"""
Inference Engine - MTTS-CAN model inference with dual output (metrics + waveforms).

This module:
1. Loads MTTS-CAN model (auto-download if needed)
2. Runs inference on preprocessed batches
3. Outputs raw pulse and respiration signals
4. Integrates with postprocessor for waveform generation

Reference:
- rppg-web: Model inference and waveform generation
- MTTS-CAN: Multi-Task Temporal Shift Convolutional Attention Network
"""

import tensorflow as tf
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
import urllib.request
from tqdm import tqdm

logger = logging.getLogger(__name__)


class InferenceEngine:
    """
    MTTS-CAN model inference engine.
    
    Attributes:
        model_path (Path): Path to model weights file
        model (tf.keras.Model): Loaded TensorFlow model
        batch_size (int): Inference batch size
        inference_count (int): Number of inferences performed
    """
    
    # Model download URL
    MODEL_URL = "https://github.com/xliucs/MTTS-CAN/releases/download/v1.0/mtts_can.hdf5"
    
    def __init__(
        self,
        model_path: str = "models/mtts_can.hdf5",
        batch_size: int = 10,
        auto_download: bool = True
    ):
        """
        Initialize inference engine.
        
        Args:
            model_path: Path to MTTS-CAN model weights
            batch_size: Batch size for inference (default: 10)
            auto_download: Auto-download model if not found (default: True)
        """
        self.model_path = Path(model_path)
        self.batch_size = batch_size
        self.auto_download = auto_download
        
        # Ensure model exists
        self._ensure_model_exists()
        
        # Load model
        self.model = self._load_model()
        
        # Statistics
        self.inference_count = 0
        
        logger.info(
            f"InferenceEngine initialized: "
            f"model={self.model_path.name}, "
            f"batch_size={batch_size}"
        )
    
    def _ensure_model_exists(self) -> None:
        """
        Ensure model file exists, download if needed.
        
        Raises:
            FileNotFoundError: If model not found and auto_download disabled
        """
        if self.model_path.exists():
            logger.info(f"✓ Model found: {self.model_path}")
            size_mb = self.model_path.stat().st_size / (1024 * 1024)
            logger.info(f"  Size: {size_mb:.1f} MB")
            return
        
        if not self.auto_download:
            raise FileNotFoundError(
                f"Model not found: {self.model_path}\n"
                f"Please download manually or enable auto_download in config.yaml\n"
                f"Download URL: {self.MODEL_URL}"
            )
        
        logger.warning(f"Model not found: {self.model_path}")
        logger.info("Downloading MTTS-CAN model...")
        
        try:
            self._download_model()
            logger.info(f"✓ Model downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise FileNotFoundError(
                f"Could not download model from {self.MODEL_URL}\n"
                f"Please download manually to {self.model_path}\n"
                f"Error: {e}"
            )
    
    def _download_model(self) -> None:
        """Download MTTS-CAN model with progress bar."""
        # Create models directory
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
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
            desc="Model"
        ) as t:
            urllib.request.urlretrieve(
                self.MODEL_URL,
                filename=self.model_path,
                reporthook=t.update_to
            )
    
    def _load_model(self) -> tf.keras.Model:
        """
        Load MTTS-CAN model from HDF5 file.
        
        Returns:
            Loaded TensorFlow Keras model
        
        Raises:
            RuntimeError: If model loading fails
        """
        try:
            logger.info(f"Loading model: {self.model_path}...")
            
            # Load model
            model = tf.keras.models.load_model(
                str(self.model_path),
                compile=False  # Don't need compilation for inference
            )
            
            # Log model info
            logger.info("✓ Model loaded successfully")
            logger.info(f"  Input shape: {model.input_shape}")
            logger.info(f"  Output shape: {model.output_shape}")
            
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(
                f"Could not load model from {self.model_path}\n"
                f"File may be corrupted. Try deleting and re-downloading.\n"
                f"Error: {e}"
            )
    
    def infer_batch(
        self,
        diff_batch: np.ndarray,
        app_batch: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run inference on single batch.
        
        Args:
            diff_batch: Difference frames (batch_size, 36, 36, 3)
            app_batch: Appearance frames (batch_size, 36, 36, 3)
        
        Returns:
            Tuple of:
            - pulse_raw: Raw pulse signal (batch_size, temporal_dim)
            - resp_raw: Raw respiration signal (batch_size, temporal_dim)
        
        Raises:
            ValueError: If batch shapes are incorrect
        
        Example:
            >>> engine = InferenceEngine()
            >>> pulse, resp = engine.infer_batch(diff_batch, app_batch)
            >>> print(pulse.shape)  # (10, temporal_dim)
        """
        # Validate input shapes
        expected_shape = (self.batch_size, 36, 36, 3)
        if diff_batch.shape != expected_shape:
            raise ValueError(
                f"Invalid diff_batch shape: {diff_batch.shape}, "
                f"expected {expected_shape}"
            )
        if app_batch.shape != expected_shape:
            raise ValueError(
                f"Invalid app_batch shape: {app_batch.shape}, "
                f"expected {expected_shape}"
            )
        
        # Validate data types
        if diff_batch.dtype != np.float32:
            logger.warning(
                f"diff_batch dtype is {diff_batch.dtype}, converting to float32"
            )
            diff_batch = diff_batch.astype(np.float32)
        
        if app_batch.dtype != np.float32:
            logger.warning(
                f"app_batch dtype is {app_batch.dtype}, converting to float32"
            )
            app_batch = app_batch.astype(np.float32)
        
        try:
            # Run model inference
            # MTTS-CAN expects two inputs: [difference_frames, appearance_frames]
            predictions = self.model.predict(
                [diff_batch, app_batch],
                batch_size=self.batch_size,
                verbose=0
            )
            
            # Extract signals from predictions
            # Model output shape: (batch_size, temporal_dim, 2)
            # Channel 0: Pulse signal
            # Channel 1: Respiration signal
            pulse_raw = predictions[:, :, 0]  # (batch_size, temporal_dim)
            resp_raw = predictions[:, :, 1]   # (batch_size, temporal_dim)
            
            self.inference_count += 1
            
            logger.debug(
                f"Inference {self.inference_count}: "
                f"pulse shape={pulse_raw.shape}, "
                f"resp shape={resp_raw.shape}"
            )
            
            return pulse_raw, resp_raw
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise RuntimeError(
                f"Model inference error: {e}\n"
                f"Input shapes: diff={diff_batch.shape}, app={app_batch.shape}"
            )
    
    def get_stats(self) -> Dict:
        """
        Get inference statistics.
        
        Returns:
            Dictionary with:
            - inference_count: Number of inferences performed
            - model_path: Path to model file
            - batch_size: Inference batch size
        """
        return {
            'inference_count': self.inference_count,
            'model_path': str(self.model_path),
            'batch_size': self.batch_size
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"InferenceEngine("
            f"model={self.model_path.name}, "
            f"batch_size={self.batch_size}, "
            f"inferences={self.inference_count})"
        )


class InferenceError(Exception):
    """Custom exception for inference errors."""
    pass