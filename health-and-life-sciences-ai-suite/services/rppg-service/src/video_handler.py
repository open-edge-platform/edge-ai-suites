import cv2
import numpy as np
import time
import logging
import urllib.request
"""
Video Handler - Manages pre-recorded video input with auto-download support.

This module replaces rppg-web's webcam capture (getUserMedia API) with 
file-based video input while maintaining the same frame rate and RGB format.

Key Features:
- Auto-downloads sample video if not found
- FPS control to simulate real-time streaming
- Loop playback for continuous demo
- RGB output format (compatible with rppg-web preprocessing)

Reference:
- rppg-web: src/pages/index.tsx (webcamRef.current.getScreenshot())
"""

import cv2
import numpy as np
from pathlib import Path
import logging
import time
import urllib.request
from tqdm import tqdm
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class VideoHandler:
    """
    Handles pre-recorded video input with real-time simulation.
    
    Attributes:
        video_path (Path): Path to video file
        target_fps (int): Target frames per second for playback
        loop (bool): Whether to loop video when it ends
        auto_download (bool): Auto-download sample if file not found
        cap (cv2.VideoCapture): OpenCV video capture object
        frame_count (int): Number of frames processed
    """
    
    # Default sample video URL (OpenCV test video)
    # You can replace with your own hosted video
    DEFAULT_SAMPLE_URL = "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi"
    
    def __init__(
        self,
        video_path: str,
        target_fps: int = 30,
        loop: bool = True,
        auto_download: bool = True,
        sample_url: Optional[str] = None
    ):
        """
        Initialize video handler.
        
        Args:
            video_path: Path to video file
            target_fps: Target frames per second for playback (default: 30)
            loop: Whether to loop video when it ends (default: True)
            auto_download: Auto-download sample if not found (default: True)
            sample_url: Custom URL for sample video (uses default if None)
        """
        self.video_path = Path(video_path)
        self.target_fps = target_fps
        self.loop = loop
        self.auto_download = auto_download
        self.sample_url = sample_url or self.DEFAULT_SAMPLE_URL
        
        # Video capture object (initialized in start_stream)
        self.cap: Optional[cv2.VideoCapture] = None
        
        # Frame timing control
        self.frame_interval = 1.0 / target_fps  # Time between frames
        self.last_frame_time = 0.0
        
        # Statistics
        self.frame_count = 0
        self.total_frames = 0
        
        # Ensure video exists (download if needed)
        self._ensure_video_exists()
        
        # Validate video file
        self._validate_video()
    
    def _ensure_video_exists(self) -> None:
        """
        Ensure video file exists, download if needed and enabled.
        
        Raises:
            FileNotFoundError: If video not found and auto_download disabled
        """
        if self.video_path.exists():
            logger.info(f"✓ Video found: {self.video_path}")
            return
        
        if not self.auto_download:
            raise FileNotFoundError(
                f"Video not found: {self.video_path}\n"
                f"Please provide a video file or enable auto_download in config.yaml"
            )
        
        logger.warning(f"Video not found: {self.video_path}")
        logger.info("Downloading sample video...")
        
        try:
            self._download_sample_video()
            logger.info(f"✓ Sample video downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download sample video: {e}")
            raise FileNotFoundError(
                f"Could not download sample video from {self.sample_url}\n"
                f"Please manually place a video file at {self.video_path}\n"
                f"Error: {e}"
            )
    
    def _download_sample_video(self) -> None:
        """
        Download sample video with progress bar.
        
        Uses urllib to download file with tqdm progress bar.
        """
        # Create directory if it doesn't exist
        self.video_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with progress bar
        class DownloadProgressBar(tqdm):
            def update_to(self, b=1, bsize=1, tsize=None):
                if tsize is not None:
                    self.total = tsize
                self.update(b * bsize - self.n)
        
        with DownloadProgressBar(
            unit='B',
            unit_scale=True,
            miniters=1,
            desc=self.video_path.name
        ) as t:
            urllib.request.urlretrieve(
                self.sample_url,
                filename=self.video_path,
                reporthook=t.update_to
            )
    
    def _validate_video(self) -> None:
        """
        Validate video file is readable and log metadata.
        
        Checks:
        - File can be opened by OpenCV
        - Resolution is adequate (>100x100)
        - Has sufficient frames (warning if <30)
        
        Raises:
            ValueError: If video cannot be opened or resolution too low
        """
        cap = cv2.VideoCapture(str(self.video_path))
        
        if not cap.isOpened():
            raise ValueError(
                f"Cannot open video: {self.video_path}\n"
                f"File may be corrupted or unsupported format."
            )
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        # Validate minimum requirements
        if width < 100 or height < 100:
            raise ValueError(
                f"Video resolution too low: {width}x{height}\n"
                f"Minimum required: 100x100"
            )
        
        if frame_count < 30:
            logger.warning(
                f"Video is very short ({frame_count} frames, {duration:.1f}s). "
                f"Consider using a longer video for better results."
            )
        
        # Store total frames for progress tracking
        self.total_frames = frame_count
        
        # Log video metadata
        logger.info("=" * 70)
        logger.info("Video Metadata:")
        logger.info(f"  Path:         {self.video_path}")
        logger.info(f"  Resolution:   {width}x{height}")
        logger.info(f"  Native FPS:   {fps:.2f}")
        logger.info(f"  Total Frames: {frame_count}")
        logger.info(f"  Duration:     {duration:.2f}s")
        logger.info(f"  Playback FPS: {self.target_fps} (controlled)")
        logger.info("=" * 70)
        
        cap.release()
    
    def start_stream(self) -> None:
        """
        Initialize video capture stream.
        
        Opens video file with OpenCV and resets frame counter.
        """
        if self.cap is not None:
            logger.warning("Stream already started")
            return
        
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video_path}")
        
        self.last_frame_time = time.time()
        self.frame_count = 0
        
        logger.info("✓ Video stream started")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get next frame with FPS control to simulate real-time playback.
        
        This method:
        1. Controls frame rate to match target_fps (throttling)
        2. Returns frames in RGB format (rppg-web uses RGB, OpenCV uses BGR)
        3. Handles video looping if enabled
        
        Returns:
            Frame as RGB numpy array shape (H, W, 3) with dtype uint8,
            or None if video ended and loop=False
            
        Example:
            >>> handler = VideoHandler("video.mp4", target_fps=30)
            >>> handler.start_stream()
            >>> frame = handler.get_frame()
            >>> print(frame.shape)  # (480, 640, 3)
            >>> print(frame.dtype)  # uint8
        """
        if self.cap is None:
            self.start_stream()
        
        # FPS throttling - simulate real-time playback
        # This ensures frames are delivered at target_fps rate
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        
        if elapsed < self.frame_interval:
            sleep_time = self.frame_interval - elapsed
            time.sleep(sleep_time)
        
        # Read frame from video
        ret, frame = self.cap.read()
        
        if not ret:
            # End of video reached
            if self.loop:
                logger.info("End of video reached, looping...")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.frame_count = 0
                ret, frame = self.cap.read()
                
                if not ret:
                    raise RuntimeError(
                        "Failed to read frame after loop reset. "
                        "Video file may be corrupted."
                    )
            else:
                logger.info("Video playback complete")
                return None
        
        # Convert BGR (OpenCV default) to RGB (rppg-web format)
        # Why: rppg-web expects RGB from webcam, we match that format
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Update timing and counters
        self.last_frame_time = time.time()
        self.frame_count += 1
        
        # Log progress periodically
        if self.frame_count % 300 == 0:  # Every 10 seconds at 30 FPS
            progress = (self.frame_count / self.total_frames) * 100
            logger.debug(
                f"Processed {self.frame_count}/{self.total_frames} frames "
                f"({progress:.1f}%)"
            )
        
        return frame_rgb
    
    def get_metadata(self) -> Dict[str, any]:
        """
        Get video metadata without starting stream.
        
        Returns:
            Dictionary with video properties:
            - path (str): Video file path
            - fps (float): Native frames per second
            - width (int): Frame width in pixels
            - height (int): Frame height in pixels
            - frame_count (int): Total number of frames
            - duration (float): Video duration in seconds
        """
        cap = cv2.VideoCapture(str(self.video_path))
        
        metadata = {
            'path': str(self.video_path),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        }
        
        cap.release()
        return metadata
    
    def stop_stream(self) -> None:
        """
        Release video capture resources and cleanup.
        
        Should be called when done processing video.
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info(
                f"✓ Video stream stopped "
                f"(processed {self.frame_count} frames)"
            )
    
    def reset(self) -> None:
        """
        Reset video to beginning without stopping stream.
        
        Useful for restarting processing without releasing resources.
        Why each part?

Auto-download: Like npm install downloads dependencies, we download video/model
FPS throttling: Simulates real-time even though video is pre-recorded
RGB conversion: Matches rppg-web's webcam RGB format
Logging: Detailed info for debugging
Context manager: with VideoHandler() as vh: pattern for clean resource management
        """
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.frame_count = 0
            logger.info("Video reset to beginning")
    
    def __enter__(self):
        """Context manager entry - starts stream."""
        self.start_stream()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stops stream."""
        self.stop_stream()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"VideoHandler(path={self.video_path}, "
            f"fps={self.target_fps}, "
            f"frames={self.frame_count}/{self.total_frames})"
        )