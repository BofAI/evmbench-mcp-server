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
    from fastmcp.utilities.lifespan import combine_lifespans

    from api.mcp import mcp_server, set_fastapi_app

    _mcp_http_app = mcp_server.http_app(path='/')
    _lifespan = combine_lifespans(lifespan, _mcp_http_app.lifespan)


app = FastAPI(
    docs_url='/' if settings.BACKEND_DEV else None,
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
app.include_router(v1_router)

if settings.BACKEND_MCP_ENABLED:
    set_fastapi_app(app)

    _mcp_mount = _mcp_http_app
    if settings.BACKEND_MCP_API_KEY is not None:
        from api.mcp.auth import McpApiKeyMiddleware

        _mcp_mount = McpApiKeyMiddleware(  # type: ignore[assignment]
            _mcp_http_app,
            api_key=settings.BACKEND_MCP_API_KEY.get_secret_value(),
        )

    app.mount('/mcp', _mcp_mount)
