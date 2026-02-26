"""MCP server embedded in the evmbench backend.

Exposes audit capabilities as MCP tools via Streamable HTTP at /mcp.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from api.mcp.tools import (
    tool_get_frontend_config,
    tool_get_job_history,
    tool_get_job_status,
    tool_set_job_public,
    tool_start_job,
)


if TYPE_CHECKING:
    from fastapi import FastAPI

# streamable_http_path='/' so that when client requests .../mcp/, child gets path "/" and Route("/") matches.
# Keep SSE (default): do not set json_response=True so standard MCP clients (Claude Desktop, Cursor) work.
# If session.initialize() hangs, the server may not be closing the SSE stream after the response; consider
# json_response=True only for serverless/short requests or until the SDK fixes SSE stream closure.
mcp_server = FastMCP(
    'evmbench',
    instructions=(
        'evmbench is a smart-contract security audit service. '
        'Upload a Solidity project (zip) to start an audit, '
        'then poll job status until the vulnerability report is ready.'
    ),
    streamable_http_path='/',
)

_fastapi_app: FastAPI | None = None


def set_fastapi_app(app: FastAPI) -> None:
    global _fastapi_app  # noqa: PLW0603
    _fastapi_app = app


# ---------------------------------------------------------------------------
# Register tools
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name='start_job',
    description=(
        'Start a smart-contract audit job. '
        'Accepts a base64-encoded zip of Solidity source files. '
        'Returns job_id and initial status (queued).'
    ),
)
async def mcp_start_job(
    file_base64: str,
    file_name: str,
    model: str,
    openai_key: str | None = None,
) -> dict:
    try:
        return await tool_start_job(
            file_base64=file_base64,
            file_name=file_name,
            model=model,
            openai_key=openai_key,
            app_state=_fastapi_app.state if _fastapi_app else None,
        )
    except Exception as err:
        logging.getLogger(__name__).exception('MCP tool start_job failed: %s', err)
        raise


@mcp_server.tool(
    name='get_job_status',
    description=(
        'Get the current status and result of an audit job by ID. '
        'Returns status, vulnerability report (when complete), error, queue position, timestamps.'
    ),
)
async def mcp_get_job_status(job_id: str) -> dict:
    return await tool_get_job_status(job_id=job_id)


@mcp_server.tool(
    name='get_job_history',
    description='List past audit jobs for the authenticated user.',
)
async def mcp_get_job_history() -> list[dict]:
    return await tool_get_job_history()


@mcp_server.tool(
    name='set_job_public',
    description='Toggle public visibility of an audit job.',
)
async def mcp_set_job_public(
    job_id: str,
    public: bool,  # noqa: FBT001
) -> dict:
    return await tool_set_job_public(job_id=job_id, public=public)


@mcp_server.tool(
    name='get_frontend_config',
    description='Get backend configuration info (auth mode, key mode).',
)
async def mcp_get_frontend_config() -> dict:
    return await tool_get_frontend_config()
