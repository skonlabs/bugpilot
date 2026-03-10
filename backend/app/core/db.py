from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

settings = get_settings()

# Supabase's transaction-mode PgBouncer (port 6543) does not support prepared
# statements. Disable the asyncpg cache when connecting via the pooler.
_url = settings.DATABASE_URL
_is_supabase_pooler = "pooler.supabase.com" in _url or (
    "supabase" in _url and ":6543/" in _url
)
_connect_args = {"prepared_statement_cache_size": 0} if _is_supabase_pooler else {}

engine = create_async_engine(
    _url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
