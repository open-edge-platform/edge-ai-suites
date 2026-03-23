import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from core.models import AITask 

# --- Database Fixtures ---

@pytest.fixture(scope="session")
def engine():
    """
    Create a database engine.
    Uses StaticPool to ensure all connections share the same in-memory SQLite database.
    """
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, 
    )

@pytest.fixture
def mock_db_session(engine):
    """
    Mock the database session.
    1. Reset database tables before each test.
    2. Create an isolated session.
    3. Override the FastAPI get_db dependency.
    4. Clean up after the test.
    """
    # 1. Reset database tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # 2. Create an independent Session
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    # 3. Inject dependency override into FastAPI
    app.dependency_overrides[get_db] = lambda: session
    
    yield session
    
    # 4. Cleanup: Close session and clear overrides
    session.close()
    app.dependency_overrides.clear()

@pytest.fixture
def client(mock_db_session):
    """
    Provide a TestClient with the mocked database session injected.
    """
    return TestClient(app)

# --- Infrastructure Mocks ---

@pytest.fixture
def mock_redis():
    """
    Global Mock for Redis client.
    The path points to services.task_service because that's where it is imported.
    """
    with patch("services.task_service.redis_client") as m:
        # Default ping to return True to simulate a healthy connection
        m.ping.return_value = True
        yield m

@pytest.fixture
def mock_ai_processor():
    """
    Global Mock for synchronous AI logic.
    The path points to services.task_service where the logic is invoked.
    """
    with patch("services.task_service.run_dummy_ai_logic", new_callable=AsyncMock) as m:
        # Set a default mock result for successful AI processing
        m.return_value = {"summary": "Mocked AI Result", "status": "success"}
        yield m