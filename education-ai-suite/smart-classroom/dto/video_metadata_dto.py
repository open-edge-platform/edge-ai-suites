from pydantic import BaseModel
from typing import Optional

class VideoMetadataRequest(BaseModel):
    session_id: str
    video_file_path: str

class VideoDurationRequest(BaseModel):
    duration: float

