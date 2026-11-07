import logging
import os
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.core.models import Base

logger = logging.getLogger(__name__)

def normalize_database_url(url: str) -> str:
    """Normalize database URL for async drivers."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://") and not url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

# Resolve database URL ensuring async driver is used
db_url = normalize_database_url(settings.DATABASE_URL)

# Configure engine parameters depending on DB backend (SQLite vs PostgreSQL)
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True
}

if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"timeout": 60}
else:
    # Production PostgreSQL pool configuration
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    # Required for transaction poolers like Supabase Supavisor / PgBouncer
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}

engine = create_async_engine(
    db_url,
    **engine_kwargs
)

if "sqlite" in db_url:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=60000;")
        cursor.close()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def run_alembic_upgrade(connection):
    from alembic.config import Config
    from alembic import command
    alembic_ini_path = str(settings.BASE_DIR / "alembic.ini")
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")

async def init_db():
    """Initializes tables and runs Alembic migrations."""
    # Ensure data directory exists
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(run_alembic_upgrade)
    except OSError as e:
        if "Network is unreachable" in str(e) or getattr(e, "errno", None) == 101:
            logger.error(
                "CRITICAL DATABASE CONNECTION ERROR: Network is unreachable! "
                "If using Supabase on Render, the direct hostname (db.*.supabase.co) resolves to IPv6 only, "
                "which Render does not route. Switch your DATABASE_URL in Render to use the Supabase IPv4 Connection Pooler: "
                "Supabase Dashboard -> Project Settings -> Database -> Connection string -> Connection Pooler (aws-0-*.pooler.supabase.com:6543 or :5432)."
            )
        raise

async def get_db():
    """FastAPI dependency for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
