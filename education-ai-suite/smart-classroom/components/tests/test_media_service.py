"""
Test script for MediaService
"""

from components.va import MediaService
import time

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
