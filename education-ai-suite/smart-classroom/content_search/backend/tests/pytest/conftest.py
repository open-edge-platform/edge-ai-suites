import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app

@pytest.fixture(scope="session")
def engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, 
    )

@pytest.fixture
def mock_db_session(engine):
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    app.dependency_overrides[get_db] = lambda: session
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

@pytest.fixture
def client(mock_db_session):
    return TestClient(app)

TARGET_ROUTER = "api.v1.endpoints.media" 
@pytest.fixture
def mock_storage():
    with patch(f"{TARGET_ROUTER}.storage_service", new_callable=AsyncMock) as m:
        m.upload_and_prepare_payload.return_value = {
            "file_key": "runs/5a477a66-bf88-4ebb-8cb6-0058811f5836/raw/video/default/car-detection-2min.mp4",
            "run_id": "5a477a66-bf88-4ebb-8cb6-0058811f5836"
        }
        yield m

@pytest.fixture
def mock_task_service():
    with patch(f"{TARGET_ROUTER}.task_service", new_callable=AsyncMock) as m:
        m.handle_file_upload.return_value = {
            "task_id": "c68211de-2187-4f52-b47d-f3a51a52b9ca",
            "status": "QUEUED"
        }
        yield m

@pytest.fixture
def mock_search_service():
    with patch(f"{TARGET_ROUTER}.search_service", new_callable=AsyncMock) as m:
        m.semantic_search.return_value = {
            "resource_id": "res-999",
            "type": "video",
            "name": "tutorial_01.mp4",
            "url": "https://cdn.example.com/files/tutorial_01.mp4",
            "created_at": 1709184000
        }

        m.trigger_ingest.return_value = {"status": "success"}
        yield m
