import pytest
import sys
from os.path import dirname, abspath

# Add backend directory to sys.path
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from app.db.session import SessionLocal, engine, Base

@pytest.fixture(scope="function")
def db():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
