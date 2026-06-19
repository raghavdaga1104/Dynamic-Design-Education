from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# In production, set DATABASE_URL to your Postgres connection string, e.g.:
#   postgresql+psycopg2://<user>:<password>@<host>:5432/<dbname>
# Falls back to a local SQLite file for offline/dev use.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///python_source/data/dde_auth.db"
)

# SQLite needs check_same_thread=False to work with FastAPI's threaded
# request handling. Postgres doesn't need (or accept) that argument, so
# it's only applied when DATABASE_URL is actually a sqlite URL.
connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # Postgres: keep a small connection pool and recycle connections
    # periodically so they don't go stale behind a load balancer / proxy.
    engine_kwargs.update(
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def init_db() -> None:
    """
    Create all tables registered on Base.metadata.

    Call this once at app startup, AFTER importing models.py (so the
    User model is registered on Base), e.g. in main.py:

        from database import init_db
        import models          # noqa: F401  (registers User on Base)
        init_db()

    For a production Postgres setup with evolving schemas, prefer
    Alembic migrations over this in the long run — this is fine for
    getting started / dev.
    """
    Base.metadata.create_all(bind=engine)