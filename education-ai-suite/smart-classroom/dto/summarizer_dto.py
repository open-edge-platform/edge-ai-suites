from pydantic import BaseModel

class SummaryRequest(BaseModel):
    session_id: str
