# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Auto-refresh enhancement for the Gradio UI
This creates a periodic refresh mechanism using gradio's built-in capabilities
"""
import gradio as gr
import time
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoRefreshManager:
    """Manages auto-refresh functionality for the dashboard"""
    
    def __init__(self, refresh_interval: int = 5):
        self.refresh_interval = refresh_interval
        self.is_running = False
        self.refresh_thread = None
        self.update_callbacks = []
    
    def add_update_callback(self, callback):
        """Add a callback function to be called on refresh"""
        self.update_callbacks.append(callback)
    
    def start_auto_refresh(self):
        """Start the auto-refresh mechanism"""
        if self.is_running:
            return
        
        self.is_running = True
        self.refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.refresh_thread.start()
        logger.info(f"Auto-refresh started with {self.refresh_interval}s interval")
    
    def stop_auto_refresh(self):
        """Stop the auto-refresh mechanism"""
        self.is_running = False
        if self.refresh_thread:
            self.refresh_thread.join(timeout=1.0)
        logger.info("Auto-refresh stopped")
    
    def _refresh_loop(self):
        """Internal refresh loop that runs in a separate thread"""
        while self.is_running:
            try:
                time.sleep(self.refresh_interval)
                if self.is_running:  # Check again after sleep
                    for callback in self.update_callbacks:
                        try:
                            callback()
                        except Exception as e:
                            logger.error(f"Error in refresh callback: {e}")
            except Exception as e:
                logger.error(f"Error in refresh loop: {e}")


def create_status_indicator_html() -> str:
    """Create a status indicator that shows the auto-refresh status"""
    return """
    <style>
        @keyframes pulse {
            0% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.3;
                transform: scale(1.1);
            }
            100% {
                opacity: 0.1;
                transform: scale(1);
            }
        }
    </style>
    <div id="refresh-status" style="
        position: fixed; 
        bottom: 20px; 
        right: 20px; 
        background: linear-gradient(135deg, #3b82f6, #1d4ed8); 
        color: white; 
        padding: 10px 15px; 
        border-radius: 8px; 
        font-size: 12px; 
        z-index: 1000;
        border: 1px solid #2563eb;
        box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
    ">
        <div style="display: flex; align-items: center; gap: 8px;">
            <div id="refresh-dot" style="
                width: 8px; 
                height: 8px; 
                background: white; 
                border-radius: 50%; 
                animation: pulse 1s infinite;
            "></div>
            <span style="color: white;">Auto-refresh active</span>
        </div>
    </div>

    """