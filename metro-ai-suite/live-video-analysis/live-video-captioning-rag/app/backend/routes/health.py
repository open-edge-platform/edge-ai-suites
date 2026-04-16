# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags = ["health"])


@router.get("/health",
    summary="Health check endpoint",
    response_model=dict
)
async def health():
    """
    Health check endpoint to verify that the application is running.
    """

    return {"status": "healthy", "message": "Live Video Captioning RAG application is up and running."}