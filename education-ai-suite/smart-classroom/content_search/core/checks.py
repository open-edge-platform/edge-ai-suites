# core/checks.py
import requests
from sqlalchemy import text
from database import SessionLocal
from config import settings

def check_services():
    print("🔍 Checking core service status...")

    # 1. Check PostgreSQL
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("✅ PostgreSQL connection OK")
        db.close()
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

    # 2. Check Search Service (Search Service - 9990)
    try:
        response = requests.get(settings.SEARCH_SERVICE_BASE_URL, timeout=3)
        print(f"✅ Search Service OK [{settings.SEARCH_SERVICE_BASE_URL}]")
    except Exception as e:
        print(f"❌ Search Service unreachable at {settings.SEARCH_SERVICE_BASE_URL}: {e}")
        return False

    return True