#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from utils.database import get_db
import time
from utils.storage_service import storage_service
from utils.search_service import search_service

router = APIRouter()

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if db_status == "healthy" else "error",
        "timestamp": time.time(),
        "services": {
            "database": db_status
        }
    }

@router.post("/reconcile")
async def reconcile_storage_data(db: Session = Depends(get_db)):
    results = db.execute(text("SELECT file_hash, file_name, file_path, bucket_name FROM file_assets")).fetchall()
    total_count = len(results)
    cleaned_count = 0
    for row in results:
        f_hash, f_name, f_path, f_bucket = row

        local_exists = storage_service.file_exists(f_path)
        chroma_exists = await search_service.check_file_exists(f_path, bucket_name=f_bucket)
        print(f"---")
        print(f"HASH: {f_hash}")
        print(f"NAME: {f_name}")
        print(f"PATH: {f_path}")
        print(f"local_exists: {local_exists}")
        print(f"chroma_exists: {chroma_exists}")

        if not local_exists:
            await search_service.delete_file_index(f_path, bucket_name=f_bucket)
        if not chroma_exists:
            storage_service.delete_file(f_path)
        if not local_exists or not local_exists:
            db.execute(text("DELETE FROM file_assets WHERE file_hash = :h"), {"h": f_hash})
            db.commit()
            cleaned_count += 1

    return {"status": "ok", "total": total_count, "cleaned": cleaned_count}
