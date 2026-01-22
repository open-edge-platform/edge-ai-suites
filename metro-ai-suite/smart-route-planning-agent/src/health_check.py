#!/usr/bin/env python3
"""
Health check script for AI Route Planner.
This script checks if the Gradio application is running and responsive.
"""

import requests
import sys
import time


def check_health(port=7860):
    """Check if the application is healthy by making a request to the Gradio interface."""
    try:
        # Try to connect to the Gradio interface
        response = requests.get(f"http://localhost:{port}/", timeout=5)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7860

    # Give the application some time to start
    for _ in range(30):  # Try for 30 seconds
        if check_health(port):
            print("Health check passed")
            sys.exit(0)
        time.sleep(1)

    print("Health check failed")
    sys.exit(1)
