"""
Manual test script for Phase 3 (Preprocessor).

Usage: python scripts/test_phase3.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from video_handler import VideoHandler
from preprocessor import Preprocessor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 70)
    logger.info("Phase 3 Manual Test: Video Handler + Preprocessor")
    logger.info("=" * 70)
    
    # Initialize components
    logger.info("\n1. Initializing video handler...")
    video_handler = VideoHandler(
        video_path="videos/sample.mp4",
        target_fps=30,
        auto_download=True
    )
    
    logger.info("\n2. Initializing preprocessor...")
    preprocessor = Preprocessor(
        crop_top=0.1,
        crop_left=0.3,
        crop_bottom=0.56,
        crop_right=0.7,
        image_size=36,
        batch_size=10
    )
    
    # Start processing
    logger.info("\n3. Starting video stream...")
    video_handler.start_stream()
    
    # Process frames to create 3 batches
    logger.info("\n4. Processing frames...")
    batches_created = 0
    target_batches = 3
    
    while batches_created < target_batches:
        # Get frame from video
        frame = video_handler.get_frame()
        if frame is None:
            logger.warning("Video ended before creating all batches")
            break
        
        # Add to preprocessor
        preprocessor.add_frame(frame)
        
        # Check if batch ready
        if preprocessor.has_batch():
            diff_batch, app_batch = preprocessor.get_batch()
            batches_created += 1
            
            logger.info(f"\nBatch {batches_created} created:")
            logger.info(f"  Difference batch shape: {diff_batch.shape}")
            logger.info(f"  Appearance batch shape: {app_batch.shape}")
            logger.info(f"  Difference range: [{diff_batch.min():.3f}, {diff_batch.max():.3f}]")
            logger.info(f"  Appearance range: [{app_batch.min():.3f}, {app_batch.max():.3f}]")
    
    # Stop video
    video_handler.stop_stream()
    
    # Print statistics
    logger.info("\n5. Processing Statistics:")
    stats = preprocessor.get_stats()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✓ Phase 3 test complete!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()