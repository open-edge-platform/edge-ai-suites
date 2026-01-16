#!/usr/bin/env python3
"""
Simple launcher script for traffic intelligence service.
This script handles the module path setup and launches the main application.
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path so relative imports work
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Now we can import and run the main function
if __name__ == "__main__":
    from main import main
    main()