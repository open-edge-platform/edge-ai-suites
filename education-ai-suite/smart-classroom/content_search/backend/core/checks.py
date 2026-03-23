# core/checks.py
import requests
from sqlalchemy import text
from database import SessionLocal
from core.redis_client import redis_client 
from config import settings

def check_services():
    print("🔍 Checking core service status...")
    
    # 1. Check Redis
    try:
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

    # 2. Check PostgreSQL
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("✅ PostgreSQL connection OK")
        db.close()
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

    # 3. Check Search Service (Search Service - 9990)
    try:
        response = requests.get(settings.SEARCH_SERVICE_BASE_URL, timeout=3)
        print(f"✅ Search Service OK [{settings.SEARCH_SERVICE_BASE_URL}]")
    except Exception as e:
        print(f"❌ Search Service unreachable at {settings.SEARCH_SERVICE_BASE_URL}: {e}")
        return False

    return True