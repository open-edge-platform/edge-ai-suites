#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.database import engine, Base
from api.v1.api import api_router
from utils.core_exceptions import setup_exception_handlers

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Edu-AI Orchestrator")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development. In production, specify exact origins.
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

setup_exception_handlers(app)
# app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1", tags=["Content Search"])
