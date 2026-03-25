# core/models.py
from sqlalchemy import Column, String, JSON, DateTime, Integer
from database import Base
from datetime import datetime
import uuid

class AITask(Base):
    __tablename__ = "edu_ai_tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String)
    status = Column(String, default="QUEUED")
    progress = Column(Integer, default=0, nullable=False)
    payload = Column(JSON)
    result = Column(JSON, nullable=True)
    user_id = Column(String, index=True, nullable=True, default="default_user")
    created_at = Column(DateTime, default=datetime.now)