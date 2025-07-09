import logging
from datetime import datetime
from pathlib import Path

# Create and configure the logger instance
logger = logging.getLogger('DA')
logger.setLevel(logging.DEBUG)  # Set the log level
logger.propagate = False  # Disable propagation to the root logger

# Create handlers (e.g., console and file handlers)
console_handler = logging.StreamHandler()

# Get the current time to use in the log file name
startup_time = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = f'output/log/da_{startup_time}.log'
Path(log_filename).parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(log_filename, encoding='utf-8')

# Create a formatter and set it for the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [P: %(processName)s(%(process)d)] [T: %(threadName)s(%(thread)d)] - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)
