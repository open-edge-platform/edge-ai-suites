"""
RPPG Service - Remote Photoplethysmography for Heart Rate & Respiration Monitoring

This service integrates:
- rppg-web: ML preprocessing, model inference, waveform generation
- SDC-MM-Simulator: Metric extraction (HR/RR), service architecture

Architecture:
    Video → Preprocessor → MTTS-CAN Model → Postprocessor → gRPC → Aggregator

Components:
    - video_handler.py: Video input management
    - preprocessor.py: Frame preprocessing (ROI extraction, batching)
    - inference_engine.py: MTTS-CAN model inference
    - postprocessor.py: Signal processing (waveforms + metrics)
    - grpc_server.py: Communication with aggregator
    - state_manager.py: State tracking
    - app.py: Main orchestrator
"""

__version__ = "1.0.0"
__author__ = "Health AI Suite Team"

# Package-level imports (for convenience)
from .video_handler import VideoHandler
from .preprocessor import Preprocessor

# Uncomment as modules are implemented:
# from .inference_engine import InferenceEngine
# from .postprocessor import Postprocessor
# from .grpc_server import RPPGServicer
# from .state_manager import StateManager

__all__ = [
    'VideoHandler',
    'Preprocessor',
    'InferenceEngine',
    'Postprocessor',
    'RPPGServicer',
    # 'StateManager',
]