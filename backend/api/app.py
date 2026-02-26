from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from api.core.config import settings
from api.core.rabbitmq import RabbitMQPublisher

from .routers.v1 import router as v1_router


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    publisher = RabbitMQPublisher(
        dsn=settings.RABBITMQ_DSN.get_secret_value(),
        queue=settings.rabbitmq_queue_name,
    )
    await publisher.connect()
    fastapi_app.state.rabbitmq = publisher
    try:
        yield
    finally:
        await publisher.close()


_lifespan = lifespan

if settings.BACKEND_MCP_ENABLED:
    from api.mcp import mcp_server, set_fastapi_app

    _mcp_http_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def _combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with lifespan(app):
            async with _mcp_http_app.router.lifespan_context(_mcp_http_app):
                yield

    _lifespan = _combined_lifespan


app = FastAPI(
    docs_url='/docs' if settings.BACKEND_DEV else None,
    openapi_url='/openapi.json' if settings.BACKEND_DEV else None,
    redoc_url=None,
    version='0.0.1',
    title='evmbench-backend',
    default_response_class=ORJSONResponse,
    lifespan=_lifespan,
)
app.add_middleware(
    CORSMiddleware,  # type: ignore[invalid-argument-type]
    allow_origins=[
        settings.FRONTEND_PUBLIC_URL,
        *settings.BACKEND_CORS_EXTRA_ORIGINS,
    ],
    allow_origin_regex=r'https://.*\.vercel\.app|https://.*\.paradigm\.xyz|http://(localhost|127\.0\.0\.1)(:\d+)?',
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
async def root() -> dict[str, str]:
    """Root endpoint for ALB health checks; returns 200."""
    return {'status': 'ok'}


app.include_router(v1_router)

if settings.BACKEND_MCP_ENABLED:
    set_fastapi_app(app)

    _target = _mcp_http_app
    if settings.BACKEND_MCP_API_KEY is not None:
        from api.mcp.auth import McpApiKeyMiddleware

        _target = McpApiKeyMiddleware(  # type: ignore[assignment]
            _mcp_http_app,
            api_key=settings.BACKEND_MCP_API_KEY.get_secret_value(),
        )

    # Mount directly; client must use URL with trailing slash (e.g. .../mcp/) so child gets path "/" and Route("/") matches.
    app.mount('/mcp', _target)
