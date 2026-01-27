"""
Phase 4 Test: Complete Inference Pipeline

Tests: VideoHandler → Preprocessor → InferenceEngine → Postprocessor

Usage: python scripts/test_inference.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from video_handler import VideoHandler
from preprocessor import Preprocessor
from inference_engine import InferenceEngine
from postprocessr import SignalPostprocessor
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 70)
    logger.info("Phase 4 Test: Complete Inference Pipeline")
    logger.info("=" * 70)
    
    # Initialize all components
    logger.info("\n1. Initializing components...")
    
    video_handler = VideoHandler(
        video_path="videos/sample.mp4",
        target_fps=30,
        auto_download=True
    )
    
    preprocessor = Preprocessor(batch_size=10)
    
    inference_engine = InferenceEngine(
        model_path="models/mtts_can.hdf5",
        auto_download=True
    )
    
    postprocessor = SignalPostprocessor(sampling_rate=30.0)
    
    # Start video
    logger.info("\n2. Starting video stream...")
    video_handler.start_stream()
    
    # Process 3 batches
    logger.info("\n3. Processing video and running inference...")
    start_time = time.time()
    
    for batch_num in range(3):
        logger.info(f"\n--- Batch {batch_num + 1} ---")
        
        # Collect 10 frames
        for frame_idx in range(10):
            frame = video_handler.get_frame()
            if frame is None:
                logger.error("Video ended early")
                return
            preprocessor.add_frame(frame)
        
        # Get preprocessed batch
        diff_batch, app_batch = preprocessor.get_batch()
        logger.info(f"  Preprocessed: diff={diff_batch.shape}, app={app_batch.shape}")
        
        # Run inference
        pulse_raw, resp_raw = inference_engine.infer_batch(diff_batch, app_batch)
        logger.info(f"  Inference: pulse={pulse_raw.shape}, resp={resp_raw.shape}")
        
        # Postprocess
        result = postprocessor.process_batch(pulse_raw, resp_raw)
        
        # Display results
        logger.info(f"\n  📊 Results:")
        logger.info(f"    Heart Rate:      {result['metrics']['heart_rate']:.1f} BPM")
        logger.info(f"    Respiration Rate: {result['metrics']['resp_rate']:.1f} BrPM")
        logger.info(f"    Pulse waveform:   {len(result['waveforms']['pulse'])} samples")
        logger.info(f"    Resp waveform:    {len(result['waveforms']['resp'])} samples")
    
    elapsed = time.time() - start_time
    
    # Stop video
    video_handler.stop_stream()
    
    # Print statistics
    logger.info("\n4. Pipeline Statistics:")
    logger.info(f"  Total time:        {elapsed:.2f}s")
    logger.info(f"  Batches processed: 3")
    logger.info(f"  Frames processed:  30")
    logger.info(f"  Avg time/batch:    {elapsed/3:.2f}s")
    logger.info(f"  FPS:               {30/elapsed:.1f}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✓ Phase 4 test complete!")
    logger.info("=" * 70)
    logger.info("\nNext: Implement gRPC server (Phase 6)")


if __name__ == "__main__":
    main()