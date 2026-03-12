# core/checks.py
from sqlalchemy import text
from database import SessionLocal

from core.redis_client import redis_client 

def check_services():
    print("🔍 Checking core service status...")
    
    # 1. Check Redis
    try:
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("✅ PostgreSQL connection OK")
        db.close()
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

    return True