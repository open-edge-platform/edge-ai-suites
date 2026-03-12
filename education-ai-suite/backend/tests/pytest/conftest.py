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
    # 使用 StaticPool 确保所有连接共享同一个内存数据库
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, 
    )

@pytest.fixture
def mock_db_session(engine):
    # 1. 每次测试前重置数据库表
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # 2. 创建独立 Session
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    # 3. 注入 FastAPI 依赖
    app.dependency_overrides[get_db] = lambda: session
    
    yield session
    
    # 4. 清理
    session.close()
    app.dependency_overrides.clear()

@pytest.fixture
def client(mock_db_session):
    return TestClient(app)

# --- NEW: Infrastructure Mocks (重构核心) ---

@pytest.fixture
def mock_redis():
    """
    全局 Mock Redis 客户端。
    路径指向 core.redis_client，因为所有 service 都从这里导入。
    """
    with patch("services.task_service.redis_client") as m:
        # 默认让 ping 返回 True
        m.ping.return_value = True
        yield m

@pytest.fixture
def mock_ai_processor():
    """
    全局 Mock 同步 AI 逻辑。
    路径指向 services.task_service，因为这是它被调用的地方。
    """
    with patch("services.task_service.run_dummy_ai_logic", new_callable=AsyncMock) as m:
        # 设置一个默认的模拟返回结果
        m.return_value = {"summary": "Mocked AI Result", "status": "success"}
        yield m