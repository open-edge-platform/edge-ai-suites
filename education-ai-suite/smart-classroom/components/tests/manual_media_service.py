"""
Manual driver for MediaService -- launches the real MediaMTX server and waits.

Not a unit test: it has no assertions and runs until interrupted. Run it by
hand from the repo root:

    python components/tests/manual_media_service.py
"""

import os
import sys
import time

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from components.va.media_service import MediaService

def example_basic():
    """Basic usage example"""
    # Create service instance
    media_service = MediaService()
    
    try:
        # Launch the server
        print("Starting MediaMTX server...")
        if media_service.launch_server():
            print("✓ Server started successfully\n")
            
            # Get status
            status = media_service.get_status()
            print("Server Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
            print()
            
            # Keep running for a while
            print("Server is running. Press Ctrl+C to stop...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping server...")
        else:
            print("✗ Failed to start server")
            
    finally:
        # Stop the server
        media_service.stop_server()
        print("Server stopped")


if __name__ == "__main__":
    example_basic()
