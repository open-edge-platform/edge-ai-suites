from pydantic import BaseModel
from typing import Optional

class VideoAnalyticsRequest(BaseModel):
    pipeline_name: str
    source: Optional[str] = None
