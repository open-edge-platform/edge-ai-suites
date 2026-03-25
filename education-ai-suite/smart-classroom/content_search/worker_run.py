import redis
import asyncio
from database import SessionLocal
from core.models import AITask
from processor import run_dummy_ai_logic
from core.redis_client import redis_client
from services.search_service import search_service

STREAMS = {
    "stream:video_processing": ">",
    "stream:file_search": ">"
}
GROUP_NAME = "worker_group"

async def handle_task(db, task_id, stream_name):
    if isinstance(task_id, bytes):
        task_id = task_id.decode()
    if isinstance(stream_name, bytes):
        stream_name = stream_name.decode()

    task = db.query(AITask).filter(AITask.id == task_id).first()
    if not task:
        print(f"⚠️ Task {task_id} not found in DB")
        return None

    task.status = "PROCESSING"
    db.commit()

    try:
        if stream_name == "stream:video_processing":
            file_url = task.payload.get('video_url')
            ai_result = await run_dummy_ai_logic(file_url)
            task.status = "COMPLETED"
            task.result = ai_result
        elif stream_name == "stream:file_search":
            file_key = task.payload.get('file_key') or task.payload.get('video_key')
            ai_result = await search_service.trigger_ingest(file_key) 
            task.status = "COMPLETED"
            task.result = ai_result
        else:
            ai_result = {"error": f"Unknown stream: {stream_name}"}

        db.commit()
        print(f"✅ Task {task_id} completed via {stream_name}")

        return ai_result

    except Exception as e:
        task.status = "FAILED"
        task.result = {"error": str(e)}
        db.commit()
        print(f"❌ Task {task_id} failed: {e}")
        return None

async def process_task_loop():

    for stream in STREAMS:
        try:
            redis_client.xgroup_create(stream, GROUP_NAME, mkstream=True)
        except redis.exceptions.ResponseError:
            pass

    print(f"Worker started, monitoring: {list(STREAMS.keys())}")

    while True:
        messages = await asyncio.to_thread(
            redis_client.xreadgroup, GROUP_NAME, "worker_1", STREAMS, count=1, block=2000
        )

        if not messages:
            continue

        for stream_name, msg_list in messages:
            for msg_id, data in msg_list:
                raw_id = data.get(b"task_id") or data.get("task_id")
                if not raw_id: continue
                db = SessionLocal()
                try:
                    await handle_task(db, raw_id, stream_name)
                finally:
                    db.close()
                    await asyncio.to_thread(redis_client.xack, stream_name, GROUP_NAME, msg_id)

if __name__ == "__main__":
    try:
        asyncio.run(process_task_loop())
    except KeyboardInterrupt:
        print("\n👋 Worker stopped by user.")