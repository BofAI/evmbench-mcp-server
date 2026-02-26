import uvicorn

from api.core.config import settings
from api.util.logger import logger


def main() -> None:
    logger.info(f'Starting at {settings.BACKEND_WEB_HOST}:{settings.BACKEND_WEB_PORT} {settings.BACKEND_DEV = }')

    if settings.BACKEND_DEV:
        # Single worker in dev env
        uvicorn.run(
            'api.app:app',
            host=settings.BACKEND_WEB_HOST,
            port=settings.BACKEND_WEB_PORT,
        )
        return

    workers = settings.BACKEND_WEB_WORKERS
    if settings.BACKEND_MCP_ENABLED and workers > 1:
        logger.warning(
            f'MCP is enabled but BACKEND_WEB_WORKERS={workers}. '
            'MCP Streamable HTTP sessions are stateful and stored in-process memory, '
            'so multiple workers will cause session-not-found errors. '
            'Forcing workers=1. To use multiple workers, disable MCP or put a '
            'sticky-session load balancer (keyed on mcp-session-id) in front.',
        )
        workers = 1

    uvicorn.run(
        'api.app:app',
        host=settings.BACKEND_WEB_HOST,
        port=settings.BACKEND_WEB_PORT,
        workers=workers,
        server_header=False,
    )


if __name__ == '__main__':
    main()
