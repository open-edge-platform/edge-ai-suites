# mock_services/dummy_ai_provider.py
from fastapi import FastAPI
import uvicorn
import asyncio

app = FastAPI()

@app.post("/analyze-video")
async def mock_video_analysis(payload: dict):
    video_url = payload.get("video_url", "unknown")
    print(f"📡 [Dummy AI Provider] Received analysis request: {video_url}")
    
    # Simulate AI processing time
    await asyncio.sleep(3) 
    
    return {
        "status": "success",
        "data": {
            "summary": f"This is a mock result from the local Dummy service for {video_url}.",
            "confidence": 0.98,
            "provider": "Mock-Windows-Service"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)