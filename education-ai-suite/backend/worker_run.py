import redis
import asyncio
import requests  # Used to send webhook callbacks
from database import SessionLocal
from core.models import AITask
from processor import run_dummy_ai_logic  # Import extracted logic

# 1. Connect to Redis
redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
STREAM_NAME = "stream:video_processing" 
GROUP_NAME = "worker_group"

def send_webhook(url, data):
    """Helper to send callbacks."""
    if not url:
        return
    try:
        print(f"🔗 Sending webhook callback to: {url}")
        response = requests.post(url, json=data, timeout=5)
        print(f"📬 Callback status code: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Callback send failed: {e}")

def process_task():
    # Create consumer group
    try:
        redis_client.xgroup_create(STREAM_NAME, GROUP_NAME, mkstream=True)
    except redis.exceptions.ResponseError:
        pass

    print("🚀 Lightweight worker started, waiting for tasks...")

    while True:
        messages = redis_client.xreadgroup(GROUP_NAME, "worker_1", {STREAM_NAME: ">"}, count=1, block=2000)

        if not messages:
            continue

        for _, msg_list in messages:
            for msg_id, data in msg_list:
                task_id = data.get("task_id")
                print(f"📦 Received task: {task_id}")

                db = SessionLocal()
                try:
                    task = db.query(AITask).filter(AITask.id == task_id).first()
                    if task:
                        # Update status
                        task.status = "PROCESSING"
                        db.commit()
                        
                        # --- Core logic: call the unified processor ---
                        # run_dummy_ai_logic is async, run it via asyncio.run
                        video_url = task.payload.get('video_url')
                        ai_result = asyncio.run(run_dummy_ai_logic(video_url))
                        # ------------------------------------

                        # Update result
                        task.status = "COMPLETED"
                        task.result = ai_result
                        db.commit()
                        print(f"✅ Task completed: {task_id}")

                        # --- Handle webhook callback ---
                        callback_url = task.payload.get("callback_url")
                        if callback_url:
                            callback_body = {
                                "task_id": task.id,
                                "status": "COMPLETED",
                                "result": ai_result
                            }
                            send_webhook(callback_url, callback_body)

                except Exception as e:
                    print(f"❌ Processing error: {e}")
                finally:
                    db.close()

                # Acknowledge message
                redis_client.xack(STREAM_NAME, GROUP_NAME, msg_id)

if __name__ == "__main__":
    process_task()