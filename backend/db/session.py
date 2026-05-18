import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

_raw_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_db")
# Railway/Supabase는 postgres:// 또는 postgresql:// 형식으로 제공 — asyncpg 드라이버 prefix로 변환
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
DATABASE_URL = _raw_url

# SSL only for remote DB (Supabase), not for localhost
connect_args = {}
is_remote = "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL
is_pgbouncer = ":6543" in DATABASE_URL  # Transaction Pooler 포트
if is_remote:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

if is_pgbouncer:
    # pgbouncer(Transaction Pooler)는 prepared statements 미지원
    # statement_cache_size=0 으로 비활성화
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args=connect_args,
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
