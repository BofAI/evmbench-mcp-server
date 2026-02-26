"""Transport-level API key guard for the MCP endpoint.

When BACKEND_MCP_API_KEY is set, every HTTP request to /mcp must carry
the header ``MCP-API-Key: <key>``.  If the key is unset the middleware
is a no-op pass-through.
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING


# Header name for MCP API key (ASGI headers are lowercase bytes).
MCP_API_KEY_HEADER = b'mcp-api-key'

if TYPE_CHECKING:
    from asgiref.typing import ASGIApplication, ASGIReceiveCallable, ASGISendCallable, Scope


class McpApiKeyMiddleware:
    """ASGI middleware that rejects requests without a valid MCP-API-Key header."""

    def __init__(self, app: ASGIApplication, *, api_key: str) -> None:
        self._app = app
        self._api_key = api_key

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        if scope['type'] not in ('http', 'websocket'):
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get('headers', []))
        provided = headers.get(MCP_API_KEY_HEADER, b'').decode()

        if not hmac.compare_digest(provided, self._api_key):
            if scope['type'] == 'http':
                await self._send_401(send)
            return

        await self._app(scope, receive, send)

    @staticmethod
    async def _send_401(send: ASGISendCallable) -> None:
        await send(
            {
                'type': 'http.response.start',
                'status': 401,
                'headers': [(b'content-type', b'application/json')],
            }
        )
        await send(
            {
                'type': 'http.response.body',
                'body': b'{"detail":"Invalid or missing MCP API key"}',
            }
        )
