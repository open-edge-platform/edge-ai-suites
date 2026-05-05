#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# main.py
from fastapi import FastAPI

from utils.database import engine, Base
from api.v1.api import api_router
from utils.core_exceptions import setup_exception_handlers

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Edu-AI Orchestrator")
setup_exception_handlers(app)
# app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1", tags=["Content Search"])
