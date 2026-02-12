"""
MJPEG Streaming Server for pose estimation frames
"""

import cv2
import threading
import time
from flask import Flask, Response
import numpy as np
from typing import Optional


class MJPEGStreamer:
    """MJPEG streaming server for real-time video frames"""
    
    def __init__(self, port: int = 8085, quality: int = 80):  # Changed default port to 8085
        """
        Initialize MJPEG streamer
        
        Args:
            port: HTTP port for streaming
            quality: JPEG compression quality (1-100)
        """
        self.port = port
        self.quality = quality
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.app = Flask(__name__)
        self.server_thread = None
        self.running = False
        
        # Setup Flask routes
        self.app.route('/video_feed')(self.video_feed)
        self.app.route('/health')(self.health_check)
        
    def update_frame(self, frame: np.ndarray):
        """
        Update the current frame for streaming
        
        Args:
            frame: New frame to stream (BGR format)
        """
        with self.frame_lock:
            self.current_frame = frame.copy()
    
    def generate_frames(self):
        """Generator function that yields MJPEG frames"""
        while self.running:
            with self.frame_lock:
                if self.current_frame is not None:
                    # Encode frame as JPEG
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                    ret, buffer = cv2.imencode('.jpg', self.current_frame, encode_param)
                    
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    else:
                        # Send empty frame if encoding fails
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')
                else:
                    # Send black frame if no frame available
                    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                    ret, buffer = cv2.imencode('.jpg', black_frame, encode_param)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Control frame rate (target ~20 FPS)
            time.sleep(0.05)
    
    def video_feed(self):
        """Video streaming route"""
        return Response(
            self.generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    def health_check(self):
        """Health check endpoint"""
        return {'status': 'streaming', 'port': self.port}
    
    def start_server(self):
        """Start the MJPEG streaming server in background"""
        if not self.running:
            self.running = True
            self.server_thread = threading.Thread(
                target=lambda: self.app.run(
                    host='0.0.0.0', 
                    port=self.port, 
                    debug=False,
                    threaded=True,
                    use_reloader=False
                ),
                daemon=True
            )
            self.server_thread.start()
            print(f"[INFO] MJPEG streaming started on port {self.port}")
            print(f"[INFO] Stream URL: http://localhost:{self.port}/video_feed")
    
    def stop_server(self):
        """Stop the streaming server"""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=2)
        print("[INFO] MJPEG streaming stopped")