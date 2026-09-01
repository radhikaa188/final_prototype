import os
import sys
import pytest
from os.path import dirname, abspath, join

# Ensure backend directory is in sys.path
BACKEND_DIR = dirname(dirname(abspath(__file__)))
ROOT_DIR = dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 1. Force test database environment variable BEFORE app imports
TEST_DB_PATH = join(ROOT_DIR, "test_recoverai.db")
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["TESTING"] = "1"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.session import Base, get_db
import app.db.session as session_module
from app.main import app
from app.auth.init_users import seed_default_users

# 2. Create dedicated test engine & sessionmaker
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 3. Patch session_module globals so any direct import of SessionLocal / engine uses test DB
session_module.engine = test_engine
session_module.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def enforce_test_database_isolation():
    """
    Safety guard: Verifies that tests are running against the isolated test database
    and NOT the production/application database (recoverai.db).
    """
    prod_db_path = os.path.abspath(join(ROOT_DIR, "recoverai.db"))
    active_db_url = str(test_engine.url)
    
    if active_db_url == f"sqlite:///{prod_db_path}":
        raise RuntimeError(
            "CRITICAL SAFETY ERROR: Tests cannot run against the application database (recoverai.db)! "
            "Use the isolated test database."
        )
    
    # Initialize test database schema and seed test users
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db_session:
        seed_default_users(db_session)
        
    yield
    
    # Cleanup test database file after session finishes
    try:
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
    except Exception:
        pass


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Ensures that for every test function, FastAPI dependency overrides and module globals
    point to the isolated test database session.
    """
    # Ensure tables exist in test DB
    Base.metadata.create_all(bind=test_engine)
    
    # Dependency override for FastAPI routes
    def override_get_db():
        db_session = TestingSessionLocal()
        try:
            yield db_session
        finally:
            db_session.close()
            
    app.dependency_overrides[get_db] = override_get_db
    session_module.SessionLocal = TestingSessionLocal
    session_module.engine = test_engine
    
    yield
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def db():
    """
    Yields an isolated test database session for individual test functions.
    """
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
