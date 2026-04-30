import sys
from pathlib import Path

# Add src to path if not already there
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings


# Use sync engine for Streamlit
sync_dsn = settings.postgres_dsn.replace("postgresql+asyncpg://", "postgresql://")
engine = create_engine(sync_dsn, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Get database session."""
    return SessionLocal()
