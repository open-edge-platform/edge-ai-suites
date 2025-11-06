from pydantic import BaseModel

class VideoAnalyticsRequest(BaseModel):
    pipeline_name: str
    source: str
