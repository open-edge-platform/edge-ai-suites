"""
example.py — demonstrates running two GStreamer pipelines in parallel with
state callbacks and per-pipeline FPS / latency metrics.

Run from the project root (after installing GStreamer Python bindings):

    python tests/example.py
"""

import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pipeline_manager import PipelineManager
from pipeline import PipelineState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── callbacks ─────────────────────────────────────────────────────────────────


def on_state_change(pipeline_id: str, state: PipelineState) -> None:
    logger.info("[%s] state -> %s", pipeline_id, state.value)


def on_completed(pipeline_id: str) -> None:
    logger.info("[%s] COMPLETED", pipeline_id)


def on_error(pipeline_id: str, error: str, debug: str | None = None) -> None:
    logger.error("[%s] ERROR: %s (debug: %s)", pipeline_id, error, debug)


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    manager = PipelineManager()

    # Pipeline 1 — solid colour test source, 100 frames then EOS
    launch1 = (
        "filesrc location=\"C:/Users/Administrator/Downloads/warehouse.avi\" ! decodebin3 name=src ! gvadetect device=CPU model=\"C:/Users/Administrator/Downloads/pdd_from_resources/deployment/Detection/model/model.xml\" model-instance-id=0 ! queue ! gvawatermark ! gvafpscounter ! autovideosink name=sink"
    )

    # Pipeline 2 — snow pattern, different number of frames
    launch2 = (
        "filesrc location=\"C:/Users/Administrator/Downloads/warehouse.avi\" ! decodebin3 name=src ! gvadetect device=CPU model=\"C:/Users/Administrator/Downloads/pdd_from_resources/deployment/Detection/model/model.xml\" model-instance-id=0 ! queue ! gvawatermark ! gvafpscounter ! autovideosink name=sink"
    )

    id1 = manager.create(
        launch1,
        pipeline_id="pipeline-1",
        source_element_name="src",
        sink_element_name="sink",
        on_state_change=on_state_change,
        on_completed=on_completed,
        on_error=on_error,
    )

    id2 = manager.create(
        launch2,
        pipeline_id="pipeline-2",
        source_element_name="src",
        sink_element_name="sink",
        on_state_change=on_state_change,
        on_completed=on_completed,
        on_error=on_error,
    )

    logger.info("Started pipelines: %s, %s", id1, id2)

    # Poll status for up to 10 seconds
    deadline = time.time() + 10.0
    while time.time() < deadline:
        time.sleep(0.5)
        statuses = manager.list_all()
        logger.info("─── status ───────────────────────────────────────────")
        for s in statuses:
            logger.info(
                "  %-12s  state=%-10s  fps_avg=%-6.1f  fps_now=%-6.1f  lat_avg=%.2f ms  frames=%d",
                s["id"],
                s["state"],
                s["avg_fps"],
                s["current_fps"],
                s["avg_latency_ms"],
                s["frame_count"],
            )

        all_done = all(
            s["state"] in ("COMPLETED", "ABORTED", "ERROR") for s in statuses
        )
        if all_done:
            logger.info("All pipelines finished.")
            break
    else:
        logger.warning("Timeout reached - stopping remaining pipelines.")
        manager.stop_all(graceful=False)

    # Final status
    logger.info("─── final status ─────────────────────────────────────")
    for s in manager.list_all():
        logger.info("  %s", s)

    # Clean up registry entries
    manager.remove(id1)
    manager.remove(id2)

    manager.shutdown()


if __name__ == "__main__":
    main()
