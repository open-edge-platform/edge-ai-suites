# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from backend.config import APP_PORT, UI_DIR
from backend.routes import (
    chat_router,
    model_router,
    embedding_router,
    health_router,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os


app = FastAPI(title="Live Video Captioning RAG")

# Include all API routers
app.include_router(chat_router)
app.include_router(model_router)
app.include_router(embedding_router)
app.include_router(health_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(
        ","
    ),  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=os.getenv("CORS_ALLOW_METHODS", "*").split(","),
    allow_headers=os.getenv("CORS_ALLOW_HEADERS", "*").split(","),
)

@app.get("/")
async def root() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=True)