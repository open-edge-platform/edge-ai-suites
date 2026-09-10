"""Shared GStreamer environment setup. Safe to call from any entry point that is
about to spawn a GStreamer process.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Timeout for short-lived GStreamer helper processes (gst-inspect,
# gst-discoverer). Sized for a full plugin registry rebuild on a cold file
# cache, which is the worst case these calls have to survive.
GST_SUBPROCESS_TIMEOUT = 60

# App-owned location for the plugin registry cache
GST_REGISTRY_RELPATH = Path("storage") / "gstreamer" / "registry.bin"

# Registry keys the DL Streamer and GStreamer installers write. The registry is the
# only reliable source.
_REG_DLSTREAMER = r"SOFTWARE\Intel\dlstreamer"
_REG_MACHINE_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


class GStreamerEnvError(RuntimeError):
    """Raised when DL Streamer or GStreamer cannot be located."""


def _read_hklm(key: str, name: str) -> Optional[str]:
    """Read one HKLM string value, or None when the key or value is absent."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            value, _ = winreg.QueryValueEx(handle, name)
        return os.path.expandvars(value) if value else None
    except OSError:
        return None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Failed to read registry {key}\\{name}: {e}")
        return None


def dlstreamer_install() -> Optional[dict]:
    """Locate the DL Streamer install: {'install_dir': str, 'version': str|None}.

    Prefers a live DLSTREAMER_DIR so a developer can point at another install,
    then falls back to the key the installer writes.
    """
    install_dir = os.environ.get("DLSTREAMER_DIR") or _read_hklm(
        _REG_DLSTREAMER, "InstallDir"
    )
    if not install_dir:
        return None
    return {
        "install_dir": install_dir.rstrip("\\/"),
        "version": _read_hklm(_REG_DLSTREAMER, "Version"),
    }


def gstreamer_root() -> Optional[str]:
    """Locate the GStreamer runtime root, environment first then registry."""
    root = os.environ.get("GSTREAMER_1_0_ROOT_MSVC_X86_64") or _read_hklm(
        _REG_MACHINE_ENV, "GSTREAMER_1_0_ROOT_MSVC_X86_64"
    )
    return root.rstrip("\\/") if root else None


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


def ensure_dlstreamer_env() -> dict:
    """Put the DL Streamer install on GST_PLUGIN_PATH, discovering it if needed.

    Safe to call repeatedly. Returns the resolved install info.

    Raises:
        GStreamerEnvError: DL Streamer is not installed, or its bin directory
            is missing from an otherwise-registered install.
    """
    install = dlstreamer_install()
    if not install:
        raise GStreamerEnvError(
            "DL Streamer not found. Expected DLSTREAMER_DIR in the environment or "
            rf"InstallDir under HKLM\{_REG_DLSTREAMER}."
        )

    bin_dir = Path(install["install_dir"]) / "bin"
    if not bin_dir.is_dir():
        raise GStreamerEnvError(
            f"DL Streamer install at {install['install_dir']} is incomplete: {bin_dir} does not exist."
        )

    already_configured = "GST_PLUGIN_PATH" in os.environ
    add_gst_plugin_path(bin_dir)
    os.environ.setdefault("DLSTREAMER_DIR", install["install_dir"])

    # Record which DL Streamer this process bound to. A dev box can easily have
    # more than one, and "which one am I running?" is otherwise unanswerable
    # from the logs.
    logger.info(
        f"DL Streamer {install['version'] or 'unknown'} at {install['install_dir']}"
    )
    if already_configured:
        logger.info(f"GST_PLUGIN_PATH: {os.environ['GST_PLUGIN_PATH']}")
    return install


def ensure_python_gst_env() -> None:
    """Make `import gi` work in this process. Must run BEFORE gi is imported.

    The gstreamer-python wheel vendors PyGObject inside a nested
    Lib/site-packages rather than installing it top level, and PyGObject needs
    PYGI_DLL_DIRS to find the GStreamer DLLs. Both are process-local.

    Idempotent. Nothing else in the runner's environment is required: a plain
    Gst.parse_launch plus bus loop needs no GI_TYPELIB_PATH.

    Raises:
        GStreamerEnvError: the wheel or the GStreamer runtime is missing.
    """
    if "gi" in sys.modules:
        return

    try:
        import gstreamer_python
    except ImportError as e:
        raise GStreamerEnvError(
            "The gstreamer-python package is not installed in this environment. "
        ) from e

    vendored = Path(gstreamer_python.__file__).parent / "Lib" / "site-packages"
    if not vendored.is_dir():
        raise GStreamerEnvError(
            f"gstreamer-python is installed but its bindings are missing at {vendored}."
        )
    if str(vendored) not in sys.path:
        sys.path.insert(0, str(vendored))

    root = gstreamer_root()
    if not root:
        raise GStreamerEnvError(
            "GStreamer not found. Expected GSTREAMER_1_0_ROOT_MSVC_X86_64 in the environment "
            rf"or under HKLM\{_REG_MACHINE_ENV}."
        )

    gst_bin = Path(root) / "bin"
    if not gst_bin.is_dir():
        raise GStreamerEnvError(f"GStreamer runtime is incomplete: {gst_bin} does not exist.")

    existing = [p for p in os.environ.get("PYGI_DLL_DIRS", "").split(os.pathsep) if p]
    key = os.path.normcase(os.path.normpath(str(gst_bin)))
    if not any(os.path.normcase(os.path.normpath(p)) == key for p in existing):
        os.environ["PYGI_DLL_DIRS"] = os.pathsep.join([str(gst_bin), *existing])
