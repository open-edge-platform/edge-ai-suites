from pydantic import BaseModel
from typing import Optional

class ProjectSettings(BaseModel):
    name: str
    location: str
    microphone: Optional[str] = None