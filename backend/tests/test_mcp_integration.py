"""Integration tests for MCP tools over Streamable HTTP.

Run against a live backend. Requires backend at BASE_URL (default http://127.0.0.1:1337).
Set MCP_API_KEY in env if the server requires MCP-API-Key header.

  cd backend && uv run pytest tests/test_mcp_integration.py -v

Skip if server is not reachable: tests are skipped when connection fails.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import zipfile
import httpx
import pytest

# Trailing slash avoids 307 redirect from Starlette Mount that can break SSE streaming.
MCP_BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:1337')
MCP_URL = f'{MCP_BASE_URL.rstrip("/")}/mcp/'
MCP_API_KEY = os.environ.get('MCP_API_KEY') or os.environ.get('BACKEND_MCP_API_KEY')
MCP_INIT_TIMEOUT = float(os.environ.get('MCP_INIT_TIMEOUT', '15.0'))


def _minimal_solidity_zip_base64() -> str:
    """Return base64 of a minimal zip containing one .sol file (for start_job)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('contract.sol', b'// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\ncontract C { }\n')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def _tool_result_text(result) -> str:
    """Extract text from MCP CallToolResult (result.content[0].text)."""
    if getattr(result, 'isError', False):
        return ''
    content = getattr(result, 'content', None) or []
    if not content:
        return ''
    first = content[0]
    return getattr(first, 'text', str(first))


@pytest.fixture(scope='module')
def backend_reachable():
    """Skip if backend is not reachable."""
    try:
        r = httpx.get(f'{MCP_BASE_URL.rstrip("/")}/v1/integration/frontend', timeout=2.0)
        r.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        pytest.skip(f'Backend not reachable at {MCP_BASE_URL}: {e}')


@pytest.mark.asyncio
async def test_mcp_get_frontend_config(backend_reachable):
    """Call get_frontend_config via MCP and assert structure."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    headers = {}
    if MCP_API_KEY:
        headers['MCP-API-Key'] = MCP_API_KEY
    http_client = create_mcp_http_client(headers=headers or None) if headers else None
    async with streamable_http_client(MCP_URL, http_client=http_client) as (recv, send, get_sid):
        session = ClientSession(recv, send)
        await asyncio.wait_for(session.initialize(), timeout=MCP_INIT_TIMEOUT)
        result = await session.call_tool('get_frontend_config', {})
    assert not getattr(result, 'isError', False), _tool_result_text(result)
    text = _tool_result_text(result)
    assert 'auth_enabled' in text or 'key_predefined' in text


@pytest.mark.asyncio
async def test_mcp_full_flow_get_config_then_start_job_then_status_history_set_public(backend_reachable):
    """Simulate full MCP tool flow: get_frontend_config -> start_job -> get_job_status -> get_job_history -> set_job_public."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    headers = {}
    if MCP_API_KEY:
        headers['MCP-API-Key'] = MCP_API_KEY
    http_client = create_mcp_http_client(headers=headers or None) if headers else None
    file_b64 = _minimal_solidity_zip_base64()

    async with streamable_http_client(MCP_URL, http_client=http_client) as (recv, send, get_sid):
        session = ClientSession(recv, send)
        await asyncio.wait_for(session.initialize(), timeout=MCP_INIT_TIMEOUT)

        # 1) get_frontend_config
        r0 = await session.call_tool('get_frontend_config', {})
        assert not getattr(r0, 'isError', False), _tool_result_text(r0)

        # 2) start_job
        r1 = await session.call_tool(
            'start_job',
            {
                'file_base64': file_b64,
                'file_name': 'minimal.zip',
                'model': 'codex-gpt-5.1-codex-max',
            },
        )
        assert not getattr(r1, 'isError', False), _tool_result_text(r1)
        text1 = _tool_result_text(r1)
        assert 'job_id' in text1 and 'queued' in text1

        import json
        try:
            out = json.loads(text1)
        except Exception:
            out = {}
        job_id = out.get('job_id')
        assert job_id, f'Expected job_id in start_job result: {text1}'

        # 3) get_job_status
        r2 = await session.call_tool('get_job_status', {'job_id': job_id})
        assert not getattr(r2, 'isError', False), _tool_result_text(r2)

        # 4) get_job_history
        r3 = await session.call_tool('get_job_history', {})
        assert not getattr(r3, 'isError', False), _tool_result_text(r3)

        # 5) set_job_public
        r4 = await session.call_tool('set_job_public', {'job_id': job_id, 'public': True})
        assert not getattr(r4, 'isError', False), _tool_result_text(r4)


@pytest.mark.asyncio
async def test_mcp_list_tools(backend_reachable):
    """List MCP tools and assert expected names."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    headers = {}
    if MCP_API_KEY:
        headers['MCP-API-Key'] = MCP_API_KEY
    http_client = create_mcp_http_client(headers=headers or None) if headers else None
    async with streamable_http_client(MCP_URL, http_client=http_client) as (recv, send, get_sid):
        session = ClientSession(recv, send)
        await asyncio.wait_for(session.initialize(), timeout=MCP_INIT_TIMEOUT)
        tools_result = await session.list_tools()
    names = [t.name for t in tools_result.tools]
    assert 'get_frontend_config' in names
    assert 'start_job' in names
    assert 'get_job_status' in names
    assert 'get_job_history' in names
    assert 'set_job_public' in names
