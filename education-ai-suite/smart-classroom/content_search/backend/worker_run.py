import redis
import asyncio
import requests  # Used to send webhook callbacks
from database import SessionLocal
from core.models import AITask
from processor import run_dummy_ai_logic  # Import extracted logic
from core.redis_client import redis_client

STREAMS = {
    "stream:video_processing": ">",
    "stream:file_search": ">"
}
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
    for stream in STREAMS:
        try:
            redis_client.xgroup_create(stream, GROUP_NAME, mkstream=True)
        except redis.exceptions.ResponseError:
            pass

    print(f"🚀 Worker started, monitoring: {list(STREAMS.keys())}")

    while True:
        messages = redis_client.xreadgroup(GROUP_NAME, "worker_1", STREAMS, count=1, block=2000)

        if not messages:
            continue

        for stream_name, msg_list in messages:
            for msg_id, data in msg_list:
                task_id = data.get("task_id")
                print(f"📦 [Stream: {stream_name}] Received task: {task_id}")

                db = SessionLocal()
                try:
                    task = db.query(AITask).filter(AITask.id == task_id).first()
                    if task:
                        task.status = "PROCESSING"
                        db.commit()

                        if stream_name == "stream:video_processing":
                            file_url = task.payload.get('video_url')
                            ai_result = asyncio.run(run_dummy_ai_logic(file_url))
                        
                        elif stream_name == "stream:file_search":
                            file_key = task.payload.get('file_key') or task.payload.get('video_key')
                            ai_result = {"message": f"File {file_key} is being indexed by Search Service"}

                        task.status = "COMPLETED"
                        task.result = ai_result
                        db.commit()
                        print(f"✅ Task {task_id} completed via {stream_name}")

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
                    # 确认消息已处理
                    redis_client.xack(stream_name, GROUP_NAME, msg_id)

if __name__ == "__main__":
    process_task()