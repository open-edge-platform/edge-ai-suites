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
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, 
    )

@pytest.fixture
def mock_db_session(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    app.dependency_overrides[get_db] = lambda: session

    yield session

    session.close()
    app.dependency_overrides.clear()

@pytest.fixture
def client(mock_db_session):
    return TestClient(app)

@pytest.fixture
def mock_redis():
    with patch("services.task_service.redis_client") as m:
        m.ping.return_value = True
        yield m

@pytest.fixture
def mock_ai_processor():
    with patch("services.task_service.run_dummy_ai_logic", new_callable=AsyncMock) as m:
        m.return_value = {"summary": "Mocked AI Result", "status": "success"}
        yield m