#!/usr/bin/env python3
"""Standalone script to simulate full MCP tool flow against a live backend.

Usage:
  export BASE_URL=http://127.0.0.1:1337   # optional, default above
  export MCP_API_KEY=your-key              # optional, if server requires it
  export MCP_INIT_TIMEOUT=15               # optional, seconds to wait for session.initialize()
  cd backend && uv run python scripts/mcp_integration_test.py

Requires backend running with MCP enabled at BASE_URL.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend root (same dir as this script's parent).
_env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(_env_path)

# Base URL for the backend (REST + MCP at /mcp/).
# Trailing slash avoids a 307 redirect from Starlette Mount that can break SSE streaming.
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:1337')
MCP_URL = f'{BASE_URL.rstrip("/")}/mcp/'
MCP_API_KEY = os.environ.get('MCP_API_KEY') or os.environ.get('BACKEND_MCP_API_KEY')
INIT_TIMEOUT = float(os.environ.get('MCP_INIT_TIMEOUT', '15.0'))


def _minimal_solidity_zip_base64() -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'contract.sol',
            b'// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\ncontract C { }\n',
        )
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def _tool_result_text(result) -> str:
    if getattr(result, 'isError', False):
        return ''
    content = getattr(result, 'content', None) or []
    if not content:
        return ''
    return getattr(content[0], 'text', str(content[0]))


async def main() -> int:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    def _log(msg: str) -> None:
        print(msg, flush=True)

    headers = {}
    if MCP_API_KEY:
        headers['MCP-API-Key'] = MCP_API_KEY
    http_client = create_mcp_http_client(headers=headers or None) if headers else None

    _log(f'Connecting to MCP at {MCP_URL} ...')
    async with streamable_http_client(MCP_URL, http_client=http_client) as (recv, send, get_sid):
        session = ClientSession(recv, send)
        _log('Calling session.initialize() ...')
        try:
            await asyncio.wait_for(session.initialize(), timeout=INIT_TIMEOUT)
        except asyncio.TimeoutError:
            _log(
                f'ERROR: session.initialize() timed out after {INIT_TIMEOUT}s '
                '(server may not be closing SSE stream; try MCP_INIT_TIMEOUT=30)'
            )
            return 1
        _log('session.initialize() OK')

        # 1) get_frontend_config
        _log('1) get_frontend_config')
        r0 = await session.call_tool('get_frontend_config', {})
        if getattr(r0, 'isError', False):
            _log('   ERROR: ' + _tool_result_text(r0))
            return 1
        _log('   OK: ' + _tool_result_text(r0))

        # 2) start_job
        _log('2) start_job')
        file_b64 = _minimal_solidity_zip_base64()
        r1 = await session.call_tool(
            'start_job',
            {
                'file_base64': file_b64,
                'file_name': 'minimal.zip',
                'model': 'codex-gpt-5.1-codex-max',
            },
        )
        if getattr(r1, 'isError', False):
            _log('   ERROR: ' + _tool_result_text(r1))
            return 1
        text1 = _tool_result_text(r1)
        _log('   OK: ' + text1)
        try:
            out = json.loads(text1)
            job_id = out.get('job_id')
        except Exception:
            job_id = None
        if not job_id:
            _log('   ERROR: no job_id in result')
            return 1

        # 3) get_job_status
        _log(f'3) get_job_status {job_id}')
        r2 = await session.call_tool('get_job_status', {'job_id': job_id})
        if getattr(r2, 'isError', False):
            _log('   ERROR: ' + _tool_result_text(r2))
            return 1
        _log('   OK: ' + _tool_result_text(r2))

        # 4) get_job_history
        _log('4) get_job_history')
        r3 = await session.call_tool('get_job_history', {})
        if getattr(r3, 'isError', False):
            _log('   ERROR: ' + _tool_result_text(r3))
            return 1
        _log('   OK: ' + _tool_result_text(r3))

        # 5) set_job_public
        _log(f'5) set_job_public {job_id} public=True')
        r4 = await session.call_tool('set_job_public', {'job_id': job_id, 'public': True})
        if getattr(r4, 'isError', False):
            _log('   ERROR: ' + _tool_result_text(r4))
            return 1
        _log('   OK: ' + _tool_result_text(r4))

    _log('Done. Full MCP tool flow succeeded.')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
