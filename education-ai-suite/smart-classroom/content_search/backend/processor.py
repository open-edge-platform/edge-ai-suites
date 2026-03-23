# processor.py
import httpx

async def run_dummy_ai_logic(video_url: str):
    TARGET_AI_URL = "http://127.0.0.1:8001/analyze-video"
    
    print(f"📡 [Processor] Forwarding request to AI service: {TARGET_AI_URL}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TARGET_AI_URL, 
                json={"video_url": video_url}, 
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data")
        except Exception as e:
            print(f"❌ [Processor] AI communcation failed: {e}")
            return {"error": "AI Service Unavailable"}