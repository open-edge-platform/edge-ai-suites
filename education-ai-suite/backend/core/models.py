# core/models.py
from sqlalchemy import Column, String, JSON, DateTime
from database import Base  # Ensure Base is imported from database.py
from datetime import datetime
import uuid

class AITask(Base):
    __tablename__ = "ai_tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String)
    status = Column(String, default="QUEUED")
    payload = Column(JSON)
    result = Column(JSON, nullable=True)
    user_id = Column(String, index=True, nullable=True, default="default_user")
    created_at = Column(DateTime, default=datetime.now)