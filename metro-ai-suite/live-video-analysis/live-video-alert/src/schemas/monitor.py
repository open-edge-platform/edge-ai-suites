from pydantic import BaseModel, Field
from typing import Dict, Literal

class AgentResult(BaseModel):
    """Structured Yes/No response for a single agent question"""
    answer: Literal["YES", "NO"] = Field(..., description="Must be exactly YES or NO")
    reason: str = Field(..., description="Brief explanation for the answer")

class DynamicAgentResponse(BaseModel):
    """Dynamic response containing results for multiple user-defined agents"""
    results: Dict[str, AgentResult] = Field(..., description="Dict mapping agent name to its result")

# Legacy Schema (kept for backwards compatibility)
class MonitorResponse(BaseModel):
    """Structured response from the VLM Agent (Legacy)"""
    safety: str = Field(..., description="Safety assessment results (SAFE/HAZARD)")
    fire: str = Field(..., description="Fire detection results (NO_FIRE/FIRE)")
    intrusion: str = Field(..., description="Intrusion detection results (SECURE/INTRUSION)")
