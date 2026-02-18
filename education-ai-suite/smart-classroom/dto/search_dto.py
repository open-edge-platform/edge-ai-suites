from pydantic import BaseModel

class SearchRequest(BaseModel):
    session_id: str
    query: str
    top_k: int = 5
