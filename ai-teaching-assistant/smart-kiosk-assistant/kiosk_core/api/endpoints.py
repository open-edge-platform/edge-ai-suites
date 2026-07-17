"""Kiosk-core service endpoints."""
import httpx
from fastapi import APIRouter, HTTPException

from kiosk_core import config


router = APIRouter()


@router.get("/api/v1/metrics")
def metrics() -> dict:
    """Proxy metrics payload from metrics-collector through kiosk-core."""
    try:
        with httpx.Client(timeout=4.0, trust_env=False) as client:
            response = client.get(f"{config.METRICS_COLLECTOR_URL}/metrics")
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to fetch metrics: {exc}") from exc


@router.get("/api/v1/platform-info")
def platform_info() -> dict:
    """Proxy hardware summary from metrics-collector through kiosk-core."""
    try:
        with httpx.Client(timeout=4.0, trust_env=False) as client:
            response = client.get(f"{config.METRICS_COLLECTOR_URL}/platform-info")
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to fetch platform info: {exc}") from exc
