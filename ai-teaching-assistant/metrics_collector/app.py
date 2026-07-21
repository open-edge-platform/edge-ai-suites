"""
FastAPI-based metrics HTTP server for the Smart Kiosk Assistant.

Reads metric files written by the background OS-level collectors that
supervisord (from intel/retail-benchmark) manages.

Endpoints
---------
GET /health          -> 200 {"status": "ok"}
GET /metrics         -> full time-series JSON (cpu / gpu / npu / memory / power)
GET /platform-info   -> hardware summary (processor, iGPU, NPU, memory, storage)
GET /memory          -> latest single memory snapshot
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import router


app = FastAPI(title="metrics-collector")

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the metrics API router
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("METRICS_HTTP_PORT", "9000"))
    print(
        f"[metrics-collector] starting on 0.0.0.0:{port}  "
        f"endpoints: /health  /metrics  /platform-info  /memory",
        flush=True,
    )
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
