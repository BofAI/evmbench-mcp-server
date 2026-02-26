"""Unit tests for api.mcp.tools (five MCP tools)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.job import JobStatus

from tests.conftest import make_mock_job


# ---------------------------------------------------------------------------
# tool_get_frontend_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_frontend_config_returns_dict_with_auth_and_key():
    from api.mcp import tools

    with (
        patch.object(tools, 'auth_backend', None),
        patch.object(tools.settings, 'BACKEND_STATIC_OAI_KEY', None),
        patch.object(tools.settings, 'BACKEND_USE_PROXY_STATIC_KEY', False),
    ):
        result = await tools.tool_get_frontend_config()

    assert result == {'auth_enabled': False, 'key_predefined': False}


@pytest.mark.asyncio
async def test_get_frontend_config_auth_enabled_and_key_predefined():
    from api.mcp import tools

    with (
        patch.object(tools, 'auth_backend', MagicMock()),
        patch.object(tools.settings, 'BACKEND_STATIC_OAI_KEY', MagicMock(get_secret_value=lambda: 'x')),
        patch.object(tools.settings, 'BACKEND_USE_PROXY_STATIC_KEY', False),
    ):
        result = await tools.tool_get_frontend_config()

    assert result['auth_enabled'] is True
    assert result['key_predefined'] is True


# ---------------------------------------------------------------------------
# tool_get_job_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_job_status_public_job_returns_dict(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    job = make_mock_job(job_id=job_id, public=True, user_id='other')
    mock_session.get = AsyncMock(return_value=job)
    mock_session.scalar = AsyncMock(return_value=0)

    with patch.object(tools, '_db', mock_db):
        result = await tools.tool_get_job_status(job_id=str(job_id))

    assert result['job_id'] == str(job_id)
    assert result['status'] == job.status.value
    assert result['public'] is True


@pytest.mark.asyncio
async def test_get_job_status_mcp_user_job_returns_dict(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    job = make_mock_job(job_id=job_id, public=False, user_id='mcp')
    mock_session.get = AsyncMock(return_value=job)
    mock_session.scalar = AsyncMock(return_value=0)

    with patch.object(tools, '_db', mock_db):
        result = await tools.tool_get_job_status(job_id=str(job_id))

    assert result['job_id'] == str(job_id)
    assert result['status'] == job.status.value


@pytest.mark.asyncio
async def test_get_job_status_invalid_job_id_raises():
    from api.mcp import tools

    with pytest.raises(ValueError, match='Invalid job_id'):
        await tools.tool_get_job_status(job_id='not-a-uuid')


@pytest.mark.asyncio
async def test_get_job_status_job_not_found_raises(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    mock_session.get = AsyncMock(return_value=None)

    with patch.object(tools, '_db', mock_db):
        with pytest.raises(ValueError, match='Job not found'):
            await tools.tool_get_job_status(job_id=str(job_id))


@pytest.mark.asyncio
async def test_get_job_status_private_job_wrong_user_raises(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    job = make_mock_job(job_id=job_id, public=False, user_id='other-user')
    mock_session.get = AsyncMock(return_value=job)

    with patch.object(tools, '_db', mock_db):
        with pytest.raises(ValueError, match='Job not found'):
            await tools.tool_get_job_status(job_id=str(job_id))


# ---------------------------------------------------------------------------
# tool_get_job_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_job_history_empty_returns_empty_list(mock_db, mock_session):
    from api.mcp import tools

    # Default fixture already has scalars().all() -> []; ensure it.
    mock_session.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

    with patch.object(tools, '_db', mock_db):
        result = await tools.tool_get_job_history()

    assert result == []


@pytest.mark.asyncio
async def test_get_job_history_returns_list_of_dicts(mock_db, mock_session):
    from api.mcp import tools

    j1 = make_mock_job(job_id=uuid.uuid4(), file_name='a.zip')
    j2 = make_mock_job(job_id=uuid.uuid4(), file_name='b.zip')
    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=[j1, j2])
    mock_session.scalars = AsyncMock(return_value=scalars_result)

    with patch.object(tools, '_db', mock_db):
        result = await tools.tool_get_job_history()

    assert len(result) == 2
    assert result[0]['job_id'] == str(j1.id)
    assert result[0]['file_name'] == 'a.zip'
    assert result[0]['status'] == j1.status.value
    assert 'created_at' in result[0]
    assert 'finished_at' in result[0]
    assert result[1]['job_id'] == str(j2.id)
    assert result[1]['file_name'] == 'b.zip'


# ---------------------------------------------------------------------------
# tool_set_job_public
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_job_public_success_returns_dict(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    job = make_mock_job(job_id=job_id, user_id='mcp', public=False)
    mock_session.get = AsyncMock(return_value=job)

    with patch.object(tools, '_db', mock_db):
        result = await tools.tool_set_job_public(job_id=str(job_id), public=True)

    assert result['job_id'] == str(job_id)
    assert result['public'] is True
    assert result['status'] == job.status.value
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_job_public_job_not_found_raises(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    mock_session.get = AsyncMock(return_value=None)

    with patch.object(tools, '_db', mock_db):
        with pytest.raises(ValueError, match='Job not found'):
            await tools.tool_set_job_public(job_id=str(job_id), public=True)


@pytest.mark.asyncio
async def test_set_job_public_wrong_user_raises(mock_db, mock_session):
    from api.mcp import tools

    job_id = uuid.uuid4()
    job = make_mock_job(job_id=job_id, user_id='other-user')
    mock_session.get = AsyncMock(return_value=job)

    with patch.object(tools, '_db', mock_db):
        with pytest.raises(ValueError, match='Job not found'):
            await tools.tool_set_job_public(job_id=str(job_id), public=True)


@pytest.mark.asyncio
async def test_set_job_public_invalid_job_id_raises():
    from api.mcp import tools

    with pytest.raises(ValueError, match='Invalid job_id'):
        await tools.tool_set_job_public(job_id='bad', public=True)


# ---------------------------------------------------------------------------
# tool_start_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_job_invalid_model_raises(mock_app_state):
    from api.mcp import tools

    with pytest.raises(ValueError, match='Model not allowed'):
        await tools.tool_start_job(
            file_base64='e30=',
            file_name='x.zip',
            model='invalid-model',
            app_state=mock_app_state,
        )


@pytest.mark.asyncio
async def test_start_job_success_calls_save_secret_and_publish(
    mock_db,
    mock_session,
    mock_secret_storage,
    mock_app_state,
):
    from api.mcp import tools

    mock_session.scalar = AsyncMock(return_value=None)
    mock_upload = MagicMock()
    mock_upload.file = MagicMock()
    mock_upload.file.seek = MagicMock()
    # Avoid real tarfile/bundle build; exercise job creation + save_secret + publish only.
    mock_bundle = b'fake_bundle'

    with (
        patch.object(tools, '_db', mock_db),
        patch.object(tools, 'secret_storage', mock_secret_storage),
        patch.object(tools, '_decode_upload', return_value=mock_upload),
        patch.object(tools, '_resolve_openai_token', return_value=('STATIC', 'proxy_static')),
        patch.object(tools, 'build_secret_bundle', return_value=mock_bundle),
    ):
        result = await tools.tool_start_job(
            file_base64='dummy',
            file_name='proj.zip',
            model='codex-gpt-5.1-codex-max',
            app_state=mock_app_state,
        )

    assert 'job_id' in result
    assert result['status'] == JobStatus.queued.value
    mock_secret_storage.save_secret.assert_awaited_once()
    mock_app_state.rabbitmq.publish_job_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_job_already_queued_raises(mock_db, mock_session, mock_app_state):
    from api.mcp import tools

    mock_session.scalar = AsyncMock(return_value=uuid.uuid4())
    mock_upload = MagicMock()
    mock_upload.file = MagicMock()
    mock_upload.file.seek = MagicMock()

    with (
        patch.object(tools, '_db', mock_db),
        patch.object(tools, '_decode_upload', return_value=mock_upload),
        patch.object(tools, '_resolve_openai_token', return_value=('STATIC', 'proxy_static')),
    ):
        with pytest.raises(ValueError, match='already have a queued or running job'):
            await tools.tool_start_job(
                file_base64='dummy',
                file_name='proj.zip',
                model='codex-gpt-5.1-codex-max',
                app_state=mock_app_state,
            )
