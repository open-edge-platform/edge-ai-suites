"""D1: RuntimeAggregator — normalise DLSPS status + rPPG output into a
unified analytics/rppg schema that the state store and SSE publisher consume.
"""
from __future__ import annotations

from typing import Any


class RuntimeAggregator:
    """Stateless normaliser: converts raw service payloads into the
    canonical app-state blocks used by RuntimeStateStore."""

    def __init__(self) -> None:
        self._last_hr: float | None = None
        self._last_rr: float | None = None

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def normalize(
        self,
        dlsps_status: dict[str, Any],
        rppg_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return patch dict suitable for RuntimeStateStore.patch().

        Analytics comes from the common DLSPS person/patient/latch pipeline.
        rPPG comes from the custom rPPG pipeline script result, if available.

        Args:
            dlsps_status: Raw DLSPS /pipelines/status response body.
            rppg_output:  Output from nicu_rppg_custom.RppgPipeline.process(),
                          or None when rPPG is not running yet.

        Returns:
            Dict with keys "analytics" and "rppg", ready for state.patch().
        """
        analytics = self._normalize_analytics(dlsps_status)
        rppg = self._normalize_rppg(rppg_output)
        return {"analytics": analytics, "rppg": rppg}

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _normalize_analytics(payload: dict[str, Any]) -> dict[str, Any]:
        """Map DLSPS detection fields to canonical analytics schema."""
        return {
            "patient_presence": bool(payload.get("patient_presence", False)),
            "caretaker_presence": bool(payload.get("caretaker_presence", False)),
            "latch_status": str(payload.get("latch_status", "unknown")),
        }

    def _normalize_rppg(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Map rPPG script output to canonical rppg schema.

        Holds the last valid HR/RR so that transient pipeline gaps
        don't cause null values to reach the frontend.
        """
        if not payload:
            return {
                "heart_rate_bpm": self._last_hr,
                "respiration_rate_bpm": self._last_rr,
                "signal_confidence": 0.0,
                "status": "idle",
            }

        hr = payload.get("heart_rate_bpm")
        rr = payload.get("respiration_rate_bpm")
        if hr is not None:
            self._last_hr = float(hr)
        if rr is not None:
            self._last_rr = float(rr)

        result: dict[str, Any] = {
            "heart_rate_bpm": self._last_hr,
            "respiration_rate_bpm": self._last_rr,
            "signal_confidence": float(payload.get("signal_confidence", 0.0)),
            "status": str(payload.get("status", "unknown")),
        }
        # Forward waveform arrays when present
        if payload.get("pulse_waveform"):
            result["pulse_waveform"] = payload["pulse_waveform"]
        if payload.get("resp_waveform"):
            result["resp_waveform"] = payload["resp_waveform"]
        return result
