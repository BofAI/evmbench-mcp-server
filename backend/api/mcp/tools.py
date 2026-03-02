"""MCP tool implementations.

Each tool mirrors a REST endpoint but accepts structured params.
Auth is transport-level only (MCP-API-Key header); tools run as BACKEND_MCP_SERVICE_USER_ID.
"""

from __future__ import annotations

import base64
import io
import os
import uuid
from contextlib import suppress
from typing import TYPE_CHECKING

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import and_, func, or_, select

from api.core.config import settings
from api.core.const import ALLOWED_MODELS
from api.core.deps import _db
from api.core.impl import auth_backend
from api.core.tokens import Token
from api.models.job import Job, JobStatus
from api.secrets.impl import secret_storage
from api.util.aes_gcm import derive_key, encrypt_token
from api.util.secrets_bundle import build_secret_bundle
from api.util.zip_validate import ZipValidationError, validate_upload_zip


if TYPE_CHECKING:
    from api.core.rabbitmq import RabbitMQPublisher


def _mcp_token() -> Token:
    """Return the fixed service identity for MCP tool calls."""
    uid = settings.BACKEND_MCP_SERVICE_USER_ID
    return Token(user_id=uid, login=uid, avatar_url=None)


def _get_rabbitmq(app_state: object) -> RabbitMQPublisher:
    publisher: RabbitMQPublisher | None = getattr(app_state, 'rabbitmq', None)
    if publisher is None:
        msg = 'RabbitMQ publisher not available'
        raise RuntimeError(msg)
    return publisher


def _decode_upload(file_base64: str, file_name: str) -> UploadFile:
    """Decode base64 payload into an UploadFile and validate it as a zip."""
    try:
        raw_bytes = base64.b64decode(file_base64)
    except Exception as err:
        msg = 'file_base64 is not valid base64'
        raise ValueError(msg) from err

    upload = UploadFile(file=io.BytesIO(raw_bytes), filename=file_name, size=len(raw_bytes))

    try:
        validate_upload_zip(
            upload,
            max_uncompressed_bytes=settings.BACKEND_MAX_ATTACHMENT_UNCOMPRESSED_BYTES,
            max_files=settings.BACKEND_ZIP_MAX_FILES,
            max_ratio=settings.BACKEND_ZIP_MAX_COMPRESSION_RATIO,
            require_solidity=True,
        )
    except ZipValidationError as err:
        raise ValueError(str(err)) from err

    return upload


def _resolve_openai_token(openai_key: str | None) -> tuple[str, str]:
    """Return (openai_token, key_mode) based on settings and user key."""
    use_proxy_static = settings.BACKEND_USE_PROXY_STATIC_KEY
    use_proxy_tokens = settings.BACKEND_OAI_KEY_MODE == 'proxy'

    static_key = settings.BACKEND_STATIC_OAI_KEY.get_secret_value() if settings.BACKEND_STATIC_OAI_KEY else None
    resolved_key = static_key or openai_key

    if not use_proxy_static and not resolved_key:
        msg = 'openai_key is required'
        raise ValueError(msg)

    if use_proxy_static:
        return 'STATIC', 'proxy_static'

    if use_proxy_tokens:
        if settings.OAI_PROXY_AES_KEY is None:
            msg = 'OAI_PROXY_AES_KEY must be set for proxy mode'
            raise RuntimeError(msg)
        return (
            encrypt_token(resolved_key or '', key=derive_key(settings.OAI_PROXY_AES_KEY.get_secret_value())),
            'proxy',
        )

    return resolved_key or '', 'direct'


# ---------------------------------------------------------------------------
# Tool: start_job
# ---------------------------------------------------------------------------


async def tool_start_job(
    *,
    file_base64: str,
    file_name: str,
    model: str,
    openai_key: str | None = None,
    app_state: object,
) -> dict:
    """Start a smart-contract audit job."""
    token = _mcp_token()

    allowed = model in ALLOWED_MODELS or (
        settings.AZURE_OPENAI_DEPLOYMENT is not None
        and model == f"azure-{settings.AZURE_OPENAI_DEPLOYMENT}"
    )
    if not allowed:
        msg = f'Model not allowed. Choose from: {", ".join(sorted(ALLOWED_MODELS))}'
        if settings.AZURE_OPENAI_DEPLOYMENT:
            msg += f' or azure-{settings.AZURE_OPENAI_DEPLOYMENT}'
        raise ValueError(msg)

    upload = _decode_upload(file_base64, file_name)
    openai_token, key_mode = _resolve_openai_token(openai_key)
    publisher = _get_rabbitmq(app_state)

    async with _db.acquire() as session:
        existing = await session.scalar(
            select(Job.id)
            .where(Job.user_id == token.user_id, Job.status.in_([JobStatus.queued, JobStatus.running]))
            .limit(1),
        )
        if existing is not None:
            msg = 'You already have a queued or running job'
            raise ValueError(msg)

        job_id = uuid.uuid4()
        secret_ref = os.urandom(32).hex()
        result_token = os.urandom(32).hex()

        upload.file.seek(0)
        bundle = build_secret_bundle(upload=upload, openai_token=openai_token, key_mode=key_mode)
        await secret_storage.save_secret(secret_ref, bundle)

        job = Job(
            id=job_id,
            status=JobStatus.queued,
            user_id=token.user_id,
            secret_ref=secret_ref,
            result_token=result_token,
            model=model,
            file_name=(file_name or 'files.zip')[:128],
        )
        session.add(job)
        await session.commit()

        try:
            await publisher.publish_job_start(
                job_id=str(job_id),
                secret_ref=secret_ref,
                model=model,
                result_token=result_token,
            )
        except Exception as err:
            with suppress(Exception):
                await secret_storage.delete_secret(secret_ref)
            await session.delete(job)
            await session.commit()
            msg = 'Failed to enqueue job'
            raise RuntimeError(msg) from err

    logger.info(f'MCP start_job: created job {job_id}')
    return {'job_id': str(job_id), 'status': job.status.value}


# ---------------------------------------------------------------------------
# Tool: get_job_status
# ---------------------------------------------------------------------------


async def tool_get_job_status(
    *,
    job_id: str,
) -> dict:
    """Get the status and result of an audit job.

    Args:
        job_id: UUID of the job to query.

    Returns:
        dict with job_id, status, result (vulnerability report), error, model, etc.
    """
    token = _mcp_token()

    try:
        uid = uuid.UUID(job_id)
    except ValueError as err:
        msg = f'Invalid job_id: {job_id}'
        raise ValueError(msg) from err

    async with _db.acquire() as session:
        job = await session.get(Job, uid)
        if not job:
            msg = f'Job not found: {job_id}'
            raise ValueError(msg)
        if not job.public and job.user_id != token.user_id:
            msg = f'Job not found: {job_id}'
            raise ValueError(msg)

        queue_position = None
        if job.status == JobStatus.queued and job.created_at is not None:
            count = await session.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.status == JobStatus.queued,
                    or_(
                        Job.created_at < job.created_at,
                        and_(Job.created_at == job.created_at, Job.id < job.id),
                    ),
                ),
            )
            queue_position = int(count or 0) + 1

    return {
        'job_id': str(job.id),
        'status': job.status.value,
        'result': job.result,
        'error': job.result_error,
        'model': job.model,
        'file_name': job.file_name,
        'public': job.public,
        'queue_position': queue_position,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None,
    }


# ---------------------------------------------------------------------------
# Tool: get_job_history
# ---------------------------------------------------------------------------


async def tool_get_job_history() -> list[dict]:
    """List past audit jobs for the MCP service user.

    Returns:
        list of dicts, each with job_id, status, file_name, created_at, finished_at.
    """
    token = _mcp_token()

    async with _db.acquire() as session:
        stmt = (
            select(Job)
            .where(Job.user_id == token.user_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(100)
        )
        jobs = await session.scalars(stmt)
        return [
            {
                'job_id': str(j.id),
                'status': j.status.value,
                'file_name': j.file_name,
                'created_at': j.created_at.isoformat() if j.created_at else None,
                'finished_at': j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs.all()
        ]


# ---------------------------------------------------------------------------
# Tool: set_job_public
# ---------------------------------------------------------------------------


async def tool_set_job_public(
    *,
    job_id: str,
    public: bool,
) -> dict:
    """Toggle public visibility of an audit job (must be owned by MCP service user).

    Args:
        job_id: UUID of the job.
        public: True to make the job publicly accessible, False to make it private.

    Returns:
        dict with the updated job status.
    """
    token = _mcp_token()

    try:
        uid = uuid.UUID(job_id)
    except ValueError as err:
        msg = f'Invalid job_id: {job_id}'
        raise ValueError(msg) from err

    async with _db.acquire() as session:
        job = await session.get(Job, uid)
        if not job or job.user_id != token.user_id:
            msg = f'Job not found: {job_id}'
            raise ValueError(msg)

        job.public = public
        await session.commit()
        await session.refresh(job)

    return {
        'job_id': str(job.id),
        'status': job.status.value,
        'public': job.public,
    }


# ---------------------------------------------------------------------------
# Tool: get_frontend_config
# ---------------------------------------------------------------------------


async def tool_get_frontend_config() -> dict:
    """Get backend configuration info (auth mode, key mode).

    Returns:
        dict with auth_enabled and key_predefined.
    """
    return {
        'auth_enabled': bool(auth_backend),
        'key_predefined': settings.BACKEND_STATIC_OAI_KEY is not None or settings.BACKEND_USE_PROXY_STATIC_KEY,
    }
