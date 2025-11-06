from utils.platform_info import get_platform_and_model_info
import sys
import re
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

MIN_MEMORY_GB = 32
REQUIRED_OS = "Windows 11"
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 12
REQUIRED_NODE_MAJOR = 18  # Minimum required Node.js version


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

\033[90m------------------------------------------------------------\033[0m
""")

    try:
        user_input = input("⚠️  Press ENTER to continue anyway or type 'exit' to quit: ").strip().lower()
        if user_input == "exit":
            return False
        return True
    except KeyboardInterrupt:
        return False
