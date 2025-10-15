from pydantic import BaseModel

class TranscriptionRequest(BaseModel):
    audio_filename: str
