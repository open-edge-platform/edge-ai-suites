from pydantic import BaseModel
from typing import Optional, Union

class OCRExtractRequest(BaseModel):
    """Request model for OCR text extraction."""
    session_id: Optional[str] = None


class OCRResponse(BaseModel):
    """Response model for OCR operations."""
    code: int
    data: dict
    message: str
    timestamp: Union[str, int]
