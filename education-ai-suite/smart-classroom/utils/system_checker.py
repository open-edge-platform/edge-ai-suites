from utils.platform_info import get_platform_and_model_info
import os
import sys
import re
import subprocess
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_MEMORY_GB = 32
REQUIRED_OS = "Windows 11"
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 12
REQUIRED_NODE_MAJOR = 18  # Minimum required Node.js version
MIN_DLSTREAMER_VERSION = (2026, 1, 0)


def _configure_windows_dlstreamer_environment() -> bool:
    """Activate an installed DL Streamer for the current Python process."""
    if sys.platform != "win32":
        return False

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Intel\dlstreamer"
        ) as key:
            install_dir, _ = winreg.QueryValueEx(key, "InstallDir")

        dlstreamer_bin = Path(install_dir).resolve() / "bin"
        if not dlstreamer_bin.is_dir():
            logger.error("DL Streamer bin directory not found: %s", dlstreamer_bin)
            return False

        gstreamer_root = os.environ.get("GSTREAMER_1_0_ROOT_MSVC_X86_64")
        if not gstreamer_root:
            gstreamer_root = os.environ.get("GSTREAMER_1_0_ROOT_X86_64")
        if not gstreamer_root:
            logger.error(
                "GStreamer root environment variable is not set; cannot activate DL Streamer."
            )
            return False

        gstreamer_bin = Path(gstreamer_root).resolve() / "bin"
        if not gstreamer_bin.is_dir():
            logger.error("GStreamer bin directory not found: %s", gstreamer_bin)
            return False

        existing_path = os.environ.get("PATH", "").split(os.pathsep)
        required_paths = [str(dlstreamer_bin), str(gstreamer_bin)]
        normalized_required = {os.path.normcase(path) for path in required_paths}
        remaining_paths = [
            path
            for path in existing_path
            if path and os.path.normcase(path) not in normalized_required
        ]

        os.environ["DLSTREAMER_DIR"] = str(Path(install_dir).resolve())
        os.environ["GST_PLUGIN_PATH"] = str(dlstreamer_bin)
        os.environ["PATH"] = os.pathsep.join(required_paths + remaining_paths)
        logger.info("Activated DL Streamer environment from %s", install_dir)
        return True
    except (FileNotFoundError, OSError) as error:
        logger.error("Could not activate DL Streamer from the Windows registry: %s", error)
        return False


def check_meteor_lake(processor_name: str) -> bool:
    try:
        if not processor_name:
            return False
        match = re.search(r"\b(\d{3})[A-Z]?\b", str(processor_name))
        return bool(match and match.group(1).startswith("1"))
    except Exception:
        return False


def parse_memory_gb(memory_str: str) -> float:
    try:
        if not memory_str:
            return 0
        match = re.search(r"(\d+)", str(memory_str))
        return float(match.group(1)) if match else 0
    except Exception:
        return 0


def check_python_version() -> bool:
    try:
        major = sys.version_info.major
        minor = sys.version_info.minor
        return major == REQUIRED_PYTHON_MAJOR and minor == REQUIRED_PYTHON_MINOR
    except Exception:
        return False


def check_nodejs_version() -> bool:
    """
    Checks if Node.js is installed and meets the minimum version requirement.
    Returns True if Node.js exists and version >= REQUIRED_NODE_MAJOR.
    """
    try:
        node_path = shutil.which("node")
        if node_path is None:
            logger.error("❌ Node.js is not installed or not found in PATH.")
            return False

        version_output = subprocess.check_output(["node", "--version"], text=True).strip()
        logger.info(f"✅ Node.js found: {version_output}")

        # Parse version (e.g., v18.16.0 → 18)
        match = re.match(r"v(\d+)", version_output)
        if not match:
            logger.error("⚠️ Unable to parse Node.js version output.")
            return False

        major_version = int(match.group(1))
        if major_version < REQUIRED_NODE_MAJOR:
            logger.error(f"⚠️ Node.js version {major_version} is too old. Please install Node.js v{REQUIRED_NODE_MAJOR}+.")
            return False

        return True

    except Exception as e:
        logger.error(f"⚠️ Node.js check failed: {e}")
        return False


def check_dlstreamer_installation() -> bool:
    """
    Checks if DL Streamer is installed by inspecting the gvadetect plugin.
    Returns True if DL Streamer is properly installed.
    """
    try:
        gst_inspect_path = shutil.which("gst-inspect-1.0")
        if gst_inspect_path is None and _configure_windows_dlstreamer_environment():
            gst_inspect_path = shutil.which("gst-inspect-1.0")
        if gst_inspect_path is None:
            logger.error("❌ gst-inspect-1.0 is not installed or not found in PATH.")
            return False

        result = subprocess.run(
            [gst_inspect_path, "gvadetect"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )

        if result.returncode == 0 and "gvadetect" in result.stdout.lower():
            version_match = re.search(r"Version\s+(\S+)", result.stdout)
            if version_match:
                version = version_match.group(1)
                parts = tuple(int(x) for x in re.findall(r"\d+", version))[:3]
                if parts < MIN_DLSTREAMER_VERSION:
                    min_ver_str = ".".join(str(v) for v in MIN_DLSTREAMER_VERSION)
                    logger.error(f"❌ DL Streamer version {version} is too old. Minimum required: {min_ver_str}.")
                    return False
                logger.info(f"✅ DL Streamer found and working (version {version}).")
                return True
        else:
            logger.error("❌ DL Streamer not found or not working properly.")
            return False
    except Exception as e:
        logger.error(f"⚠️ DL Streamer check failed: {e}")
        return False


def check_system_requirements() -> bool:
    """
    Checks the overall system environment for compatibility.
    Returns True only if all major requirements are satisfied.
    """
    try:
        info = get_platform_and_model_info()
    except Exception:
        return False

    try:
        if not check_meteor_lake(info.get("Processor", "")):
            return False
        if parse_memory_gb(info.get("Memory", "")) < MIN_MEMORY_GB:
            return False
        if not check_python_version():
            return False
        if not check_nodejs_version():
            return False
        if not check_dlstreamer_installation():
            return False
        return True
    except Exception:
        return False


def show_warning_and_prompt_user_to_continue():
    """
    Ask the user to press ENTER to continue or type 'exit' to quit.
    Returns True if the user wants to continue, False otherwise.
    """

    logger.warning("\n\033[1;31m⚠️  Warning: Your system doesn’t meet the minimum or recommended requirements to run this application. Please check the README for setup instructions to ensure proper execution.\033[0m")
    logger.info("""\n
\033[90m------------------------------------------------------------\033[0m             
\033[1;34m💻 System Requirements\033[0m

- \033[1mOS:\033[0m Windows 11
- \033[1mProcessor:\033[0m Intel® Core Ultra Series 1 (with integrated GPU support)
- \033[1mMemory:\033[0m 32 GB RAM (minimum recommended)
- \033[1mStorage:\033[0m At least 50 GB free (for models and logs)
- \033[1mGPU/Accelerator:\033[0m Intel® iGPU (Intel® Core Ultra Series 1, Arc GPU, or higher) for summarization acceleration
- \033[1mPython:\033[0m 3.12
- \033[1mNode.js:\033[0m v18+ (for frontend)
- \033[1mDL Streamer:\033[0m 2026.1.0+ (for video analytics pipelines)

\033[90m------------------------------------------------------------\033[0m
""")

    try:
        user_input = input("⚠️  Press ENTER to continue anyway or type 'exit' to quit: ").strip().lower()
        if user_input == "exit":
            return False
        return True
    except KeyboardInterrupt:
        return False
