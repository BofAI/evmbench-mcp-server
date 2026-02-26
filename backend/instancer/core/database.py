from api.core.database import DatabaseManager
from instancer.core.config import settings

db = DatabaseManager(
    database_url=str(settings.DATABASE_DSN.get_secret_value()),
    pool_size=settings.INSTANCER_DATABASE_POOL_SIZE,
    max_overflow=settings.INSTANCER_DATABASE_MAX_OVERFLOW,
)
