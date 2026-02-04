import cv2
import numpy as np
import logging
"""
Preprocessor - Frame preprocessing for MTTS-CAN model input.

This module ports the preprocessing pipeline from rppg-web (TypeScript) to Python:
- Face ROI extraction using crop ratios
- Resize to 36x36 pixels
- Frame differencing for temporal motion detection
- Batch formation (10 frames per batch)

Reference:
- rppg-web: src/pages/index.tsx lines 165-180
- Original paper: MTTS-CAN (Liu et al., NeurIPS 2020)

Key differences from rppg-web:
- Uses OpenCV instead of TensorFlow.js
- Handles file-based frames instead of webcam stream
- Batch processing instead of single-frame processing
"""

import cv2
import numpy as np
from collections import deque
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


class Preprocessor:
    """
    Preprocesses video frames for MTTS-CAN model inference.
    
    Pipeline:
    1. Crop face ROI using predefined ratios
    2. Resize to 36x36 pixels
    3. Compute frame difference (current - previous)
    4. Accumulate frames into batches of 10
    5. Form two tensors: difference frames and appearance frames
    
    Attributes:
        crop_top (float): Top crop ratio (0.1 = top 10%)
        crop_left (float): Left crop ratio
        crop_bottom (float): Bottom crop ratio
        crop_right (float): Right crop ratio
        image_size (int): Target size for resized frames (36x36)
        batch_size (int): Number of frames per batch (10)
        frame_buffer (deque): Rolling buffer of recent frames
    """
    
    def __init__(
        self,
        crop_top: float = 0.1,
        crop_left: float = 0.3,
        crop_bottom: float = 0.56,
        crop_right: float = 0.7,
        image_size: int = 36,
        batch_size: int = 10
    ):
        """
        Initialize preprocessor.
        
        Args:
            crop_top: Top boundary of face ROI (0.0-1.0)
            crop_left: Left boundary of face ROI (0.0-1.0)
            crop_bottom: Bottom boundary of face ROI (0.0-1.0)
            crop_right: Right boundary of face ROI (0.0-1.0)
            image_size: Target size for resized frames (default: 36)
            batch_size: Number of frames per batch (default: 10)
        
        Note:
            Crop ratios from rppg-web index.tsx:165
            These extract the forehead region which has strong pulse signal
        """
        # Crop parameters (from rppg-web)
        self.crop_top = crop_top
        self.crop_left = crop_left
        self.crop_bottom = crop_bottom
        self.crop_right = crop_right
        
        # Model input parameters
        self.image_size = image_size
        self.batch_size = batch_size
        
        # Frame buffers
        # Store processed frames (36x36 RGB)
        self.frame_buffer: deque = deque(maxlen=batch_size)
        
        # Store previous frame for difference computation
        self.previous_frame: Optional[np.ndarray] = None
        
        # Statistics
        self.frames_processed = 0
        self.batches_formed = 0
        
        logger.info(
            f"Preprocessor initialized: "
            f"ROI=[{crop_top:.2f}, {crop_left:.2f}, {crop_bottom:.2f}, {crop_right:.2f}], "
            f"size={image_size}x{image_size}, "
            f"batch_size={batch_size}"
        )
    
    def _extract_roi(self, frame: np.ndarray) -> np.ndarray:
        """
        Extract face ROI from frame using crop ratios.
        
        This extracts the forehead region which contains the strongest
        photoplethysmographic signal for heart rate detection.
        
        Args:
            frame: Input frame (H, W, 3) RGB uint8
        
        Returns:
            Cropped ROI as RGB numpy array
        
        Example:
            Frame shape: (480, 640, 3)
            Crop ratios: [0.1, 0.3, 0.56, 0.7]
            ROI: frame[48:269, 192:448, :] → (221, 256, 3)
        """
        height, width = frame.shape[:2]
        
        # Calculate pixel coordinates from ratios
        # rppg-web: const crop = image.cropAndResize([[0.1, 0.3, 0.56, 0.7]], ...)
        top = int(height * self.crop_top)
        bottom = int(height * self.crop_bottom)
        left = int(width * self.crop_left)
        right = int(width * self.crop_right)
        
        # Extract ROI
        roi = frame[top:bottom, left:right, :]
        
        return roi
    
    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Resize frame to model input size (36x36).
        
        Uses bilinear interpolation for smooth resizing.
        
        Args:
            frame: Input frame (H, W, 3) RGB uint8
        
        Returns:
            Resized frame (36, 36, 3) RGB uint8
        """
        resized = cv2.resize(
            frame,
            (self.image_size, self.image_size),
            interpolation=cv2.INTER_LINEAR
        )
        return resized
    
    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Normalize frame to [0, 1] range.
        
        Args:
            frame: Input frame uint8 [0, 255]
        
        Returns:
            Normalized frame float32 [0.0, 1.0]
        """
        return frame.astype(np.float32) / 255.0
    
    def _compute_difference(
        self,
        current: np.ndarray,
        previous: np.ndarray
    ) -> np.ndarray:
        """
        Compute frame difference for motion detection.
        
        Frame differencing highlights temporal changes (motion) which
        helps the model focus on pulse-related movements.
        
        Args:
            current: Current frame (36, 36, 3) float32 [0, 1]
            previous: Previous frame (36, 36, 3) float32 [0, 1]
        
        Returns:
            Difference frame (36, 36, 3) float32 [-1, 1]
        
        Note:
            From rppg-web: normalized_frame - previous_frame
        """
        diff = current - previous
        return diff
    
    def preprocess_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess a single frame.
        
        Pipeline:
        1. Extract face ROI
        2. Resize to 36x36
        3. Normalize to [0, 1]
        4. Compute difference with previous frame
        
        Args:
            frame: Input frame (H, W, 3) RGB uint8
        
        Returns:
            Tuple of:
            - difference_frame: (36, 36, 3) float32 (current - previous)
            - appearance_frame: (36, 36, 3) float32 (normalized current)
        
        Example:
            >>> preprocessor = Preprocessor()
            >>> diff, app = preprocessor.preprocess_frame(frame)
            >>> print(diff.shape, app.shape)
            (36, 36, 3) (36, 36, 3)
        """
        # Step 1: Extract ROI (forehead region)
        roi = self._extract_roi(frame)
        
        # Step 2: Resize to model input size
        resized = self._resize_frame(roi)
        
        # Step 3: Normalize to [0, 1]
        normalized = self._normalize_frame(resized)
        
        # Step 4: Compute difference
        if self.previous_frame is None:
            # First frame: difference is zero
            difference = np.zeros_like(normalized)
        else:
            difference = self._compute_difference(normalized, self.previous_frame)
        
        # Update previous frame for next iteration
        self.previous_frame = normalized.copy()
        
        self.frames_processed += 1
        
        return difference, normalized
    
    def add_frame(self, frame: np.ndarray) -> None:
        """
        Add a frame to the batch buffer.
        
        Preprocesses frame and adds to buffer. When buffer reaches
        batch_size (10 frames), a complete batch is ready.
        
        Args:
            frame: Input frame (H, W, 3) RGB uint8
        
        Example:
            >>> preprocessor = Preprocessor()
            >>> for i in range(10):
            ...     preprocessor.add_frame(frame)
            >>> if preprocessor.has_batch():
            ...     diff_batch, app_batch = preprocessor.get_batch()
        """
        # Preprocess frame
        diff_frame, app_frame = self.preprocess_frame(frame)
        
        # Add to buffer as tuple (difference, appearance)
        self.frame_buffer.append((diff_frame, app_frame))
        
        if len(self.frame_buffer) == self.batch_size:
            logger.debug(
                f"Batch ready: {self.batches_formed + 1} "
                f"({self.frames_processed} frames processed)"
            )
    
    def has_batch(self) -> bool:
        """
        Check if a complete batch is ready.
        
        Returns:
            True if buffer contains batch_size frames
        """
        return len(self.frame_buffer) == self.batch_size
    
    def get_batch(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get complete batch for model inference.
        
        Combines buffered frames into two tensors:
        - Difference tensor: Motion information
        - Appearance tensor: Color/intensity information
        
        Returns:
            Tuple of:
            - difference_batch: (batch_size, 36, 36, 3) float32
            - appearance_batch: (batch_size, 36, 36, 3) float32
        
        Raises:
            ValueError: If batch not ready (call has_batch() first)
        
        Note:
            This matches rppg-web's model input format
        """
        if not self.has_batch():
            raise ValueError(
                f"Batch not ready: {len(self.frame_buffer)}/{self.batch_size} frames"
            )
        
        # Separate difference and appearance frames
        diff_frames = []
        app_frames = []
        
        for diff, app in self.frame_buffer:
            diff_frames.append(diff)
            app_frames.append(app)
        
        # Stack into batches: (batch_size, height, width, channels)
        diff_batch = np.stack(diff_frames, axis=0)
        app_batch = np.stack(app_frames, axis=0)
        
        self.batches_formed += 1
        
        # Clear buffer for next batch
        self.frame_buffer.clear()
        self.previous_frame = None  # Reset for next sequence
        
        return diff_batch, app_batch
    
    def reset(self) -> None:
        """
        Reset preprocessor state.
        
        Clears buffers and resets counters. Use when starting
        a new video or restarting processing.
        """
        self.frame_buffer.clear()
        self.previous_frame = None
        self.frames_processed = 0
        self.batches_formed = 0
        logger.info("Preprocessor reset")
    
    def get_stats(self) -> dict:
        """
        Get preprocessing statistics.
        
        Returns:
            Dictionary with:
            - frames_processed: Total frames processed
            - batches_formed: Total batches created
            - buffer_size: Current buffer size
            - is_batch_ready: Whether batch is ready
        """
        return {
            'frames_processed': self.frames_processed,
            'batches_formed': self.batches_formed,
            'buffer_size': len(self.frame_buffer),
            'is_batch_ready': self.has_batch()
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Preprocessor("
            f"size={self.image_size}, "
            f"batch_size={self.batch_size}, "
            f"frames={self.frames_processed}, "
            f"batches={self.batches_formed})"
        )


class PreprocessorError(Exception):
    """Custom exception for preprocessing errors.
    Method	Purpose	Source
_extract_roi()	Extract forehead region	rppg-web cropAndResize
_resize_frame()	Scale to 36x36	rppg-web image size
_normalize_frame()	Convert to [0,1]	Standard ML preprocessing
_compute_difference()	Temporal motion	rppg-web frame differencing
preprocess_frame()	Full pipeline for one frame	Combines all steps
add_frame()	Buffer frames	Batch formation
get_batch()	Return model input	MTTS-CAN expects (10, 36, 36, 3)"""
    pass