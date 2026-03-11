import redis
from sqlalchemy import text
from database import SessionLocal
import sys

def check_services():
    print("🔍 Checking core service status...")
    
    # 1. Check Redis
    try:
        # Reuse the existing redis_client
        from api.route import redis_client
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

    # 2. Check PostgreSQL
    db = SessionLocal()
    try:
        # Run a simple SQLAlchemy query
        db.execute(text("SELECT 1"))
        print("✅ PostgreSQL connection OK")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False
    finally:
        db.close()

    return True