#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from utils.database import get_db
import time

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
