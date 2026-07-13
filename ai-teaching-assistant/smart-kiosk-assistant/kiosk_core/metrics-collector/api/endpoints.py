"""
Metrics API endpoints for the metrics-collector service.

Reads metric files written by the background OS-level collectors that
supervisord (from intel/retail-benchmark) manages:

  /tmp/results/cpu_usage.log              <- sar  (CPU %idle every 1 s)
  /tmp/results/memory_usage.log           <- free (memory every 1 s)
  /tmp/results/qmassa1-*-tool-generated.json <- qmassa (Intel GPU)
  /tmp/results/npu_usage.csv              <- Intel NPU tool (optional)
  /tmp/results/pcm.csv                    <- Intel PCM  power (optional)
"""

from fastapi import APIRouter

from metrics import (
    build_metrics_payload,
    get_platform_info,
    parse_memory_usage,
)

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/metrics")
def get_metrics() -> dict:
    """Time-series utilization data: CPU, GPU, NPU, memory, power."""
    return build_metrics_payload()


@router.get("/platform-info")
def get_platform_info_endpoint() -> dict:
    """Hardware summary: processor, iGPU, NPU, memory, storage."""
    return get_platform_info()


@router.get("/memory")
def get_memory() -> dict:
    """Latest single memory snapshot."""
    data = parse_memory_usage()
    return data if data is not None else {"error": "no memory data"}
