"""Shared fixtures and helpers for MCP tools unit tests."""

from __future__ import annotations

import os
import uuid

# Set required env before any api import loads settings.
os.environ.setdefault('DATABASE_DSN', 'postgresql+asyncpg://u:p@127.0.0.1/db')
os.environ.setdefault('RABBITMQ_DSN', 'amqp://u:p@127.0.0.1/')
os.environ.setdefault('BACKEND_JWT_SECRET', 'test-secret')
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.models.job import Job, JobStatus


def make_mock_job(
    *,
    job_id: uuid.UUID | None = None,
    status: JobStatus = JobStatus.succeeded,
    user_id: str = 'mcp',
    model: str = 'codex-gpt-5.1-codex-max',
    file_name: str = 'test.zip',
    public: bool = False,
    result: dict | None = None,
    result_error: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock that quacks like a Job for tool code (id, status.value, user_id, etc.)."""
    j = MagicMock(spec=Job)
    j.id = job_id or uuid.uuid4()
    j.status = status
    j.user_id = user_id
    j.model = model
    j.file_name = file_name
    j.public = public
    j.result = result
    j.result_error = result_error
    j.created_at = created_at or datetime.now(UTC)
    j.started_at = started_at
    j.finished_at = finished_at
    return j


@pytest.fixture
def mock_session():
    """AsyncMock session with get, scalar, scalars, add, commit, refresh, delete."""
    session = AsyncMock()
    # add/commit/refresh/delete are sync in SQLAlchemy async session
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.scalar = AsyncMock(return_value=None)
    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=[])
    session.scalars = AsyncMock(return_value=scalars_result)
    return session


@pytest.fixture
def mock_db(mock_session):
    """Mock _db whose acquire() yields mock_session."""

    @asynccontextmanager
    async def acquire():
        yield mock_session

    db = MagicMock()
    db.acquire = acquire
    return db


@pytest.fixture
def mock_secret_storage():
    """Mock secret_storage with async save_secret and delete_secret."""
    storage = MagicMock()
    storage.save_secret = AsyncMock()
    storage.delete_secret = AsyncMock()
    return storage


@pytest.fixture
def mock_publisher():
    """Mock RabbitMQ publisher with async publish_job_start."""
    pub = MagicMock()
    pub.publish_job_start = AsyncMock()
    return pub


@pytest.fixture
def mock_app_state(mock_publisher):
    """Fake app.state with rabbitmq attribute."""
    state = MagicMock()
    state.rabbitmq = mock_publisher
    return state
