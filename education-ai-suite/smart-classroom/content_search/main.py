#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# main.py
import uvicorn, sys
from fastapi import FastAPI

from utils.database import engine, Base
from api.v1.api import api_router
from utils.core_checks import check_services
from utils.core_exceptions import setup_exception_handlers

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Edu-AI Orchestrator")
setup_exception_handlers(app)
# app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1", tags=["EDU AI Tasks"])

if __name__ == "__main__":
    if not check_services():
        print("Services not ready")
        sys.exit(1)
    # develop on Windows recommand reload
    uvicorn.run("main:app", host="127.0.0.1", port=9011, reload=True)
