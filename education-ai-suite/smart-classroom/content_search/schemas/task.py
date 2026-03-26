import os
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Any
from enum import Enum
from uuid import UUID
from typing import Union

class TaskStatus(str, Enum):
    PENDING = "PENDING"  
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskCreateRequest(BaseModel):
    file_url: Optional[HttpUrl] = None
    sync: bool = False
    metadata: Optional[dict] = Field(default_factory=dict)

# 1. API request
class TaskCreateRequest(BaseModel):
    file_url: str
    sync: bool = False

    @field_validator('file_url')
    @classmethod
    def validate_video_source(cls, v: str):
        if v.startswith(('http://', 'https://')):
            return v
        if os.path.exists(v):
            return v
        raise ValueError('file_url must be a valid URL or an existing local file path')

# 2. Redis message format
class RedisTaskMessage(BaseModel):
    task_id: str
    action: str = "video_summary"

# 3. API response
class TaskResponse(BaseModel):
    task_id: Union[int, str]
    status: TaskStatus
    mode: str
    result: Optional[Any] = None