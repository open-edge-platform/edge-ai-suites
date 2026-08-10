"""Shared GStreamer environment setup. Safe to call from any entry point that is
about to spawn a GStreamer process.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Timeout for short-lived GStreamer helper processes (gst-inspect,
# gst-discoverer). Sized for a full plugin registry rebuild on a cold file
# cache, which is the worst case these calls have to survive.
GST_SUBPROCESS_TIMEOUT = 60

# App-owned location for the plugin registry cache
GST_REGISTRY_RELPATH = Path("storage") / "gstreamer" / "registry.bin"


def ensure_gst_registry() -> None:
    """Point GST_REGISTRY at an app-owned path. Safe to call repeatedly.

    A GST_REGISTRY already present in the environment is left alone, so the
    location can still be overridden from outside the app.
    """
    if os.environ.get("GST_REGISTRY"):
        return

    registry = GST_REGISTRY_RELPATH.resolve()
    registry.parent.mkdir(parents=True, exist_ok=True)
    os.environ["GST_REGISTRY"] = str(registry)
    logger.info(f"GStreamer plugin registry cache pinned to: {registry}")


def add_gst_plugin_path(plugin_path) -> None:
    """Prepend a directory to GST_PLUGIN_PATH unless it is already listed.

    Skipping duplicates keeps GST_PLUGIN_PATH stable across repeated calls, which
    keeps the plugin registry cache valid.
    """
    entry = str(Path(plugin_path).resolve())
    existing = [p for p in os.environ.get("GST_PLUGIN_PATH", "").split(os.pathsep) if p]

    key = os.path.normcase(os.path.normpath(entry))
    if any(os.path.normcase(os.path.normpath(p)) == key for p in existing):
        return

    os.environ["GST_PLUGIN_PATH"] = os.pathsep.join([entry, *existing])
