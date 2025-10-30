from utils.platform_info import get_platform_and_model_info
import sys
import re
import logging
logger = logging.getLogger(__name__)

MIN_MEMORY_GB = 32
REQUIRED_OS = "Windows 11"
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 12

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

def check_system_requirements() -> bool:
    try:
        info = get_platform_and_model_info()
    except Exception:
        # If fetching info itself fails
        return False

    try:
        if not check_meteor_lake(info.get("Processor", "")):
            return False
        if parse_memory_gb(info.get("Memory", "")) < MIN_MEMORY_GB:
            return False
        if not check_python_version():
            return False
        return True
    except Exception:
        # Any unexpected failure in checks should return False
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