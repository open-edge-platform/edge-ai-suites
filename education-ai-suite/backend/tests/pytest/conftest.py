import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
# Ensure models are imported to register Base
try:
    from core.models import AITask 
except ImportError:
    from models import AITask

# Use StaticPool so all connections share the same in-memory DB
@pytest.fixture(scope="session")
def engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, 
    )

@pytest.fixture
def mock_db_session(engine):
    # 1. Create tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # 2. Create session
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    # 3. Override FastAPI dependency
    def override_get_db():
        yield session  # Must yield the same session

    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    # 4. Cleanup
    session.close()
    app.dependency_overrides.clear()

@pytest.fixture
def client(mock_db_session):
    # Dependency override takes effect after mock_db_session
    return TestClient(app)