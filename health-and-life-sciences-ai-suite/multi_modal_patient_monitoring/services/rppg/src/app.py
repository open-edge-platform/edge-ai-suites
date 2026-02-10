"""RPPG Service - Streams both waveform and numeric vitals."""

"""RPPG Service."""

import sys
import signal
import time
import os
import yaml
import logging
from pathlib import Path
from typing import Generator
import threading

from .video_handler import VideoHandler
from .preprocessor import Preprocessor
from .inference_engine import InferenceEngine
from .postprocessor import SignalPostprocessor
from .grpc_client import RPPGGRPCClient
from .controller_start_stop import start_control_server, is_streaming_enabled

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)


class RPPGService:
    """RPPG Service."""
    
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        logger.info("=" * 70)
        logger.info("RPPG Service Starting")
        logger.info("=" * 70)
        
        self.video = VideoHandler(
            video_path=self.config['video']['input_path'],
            target_fps=self.config['video']['target_fps'],
            loop=self.config['video'].get('loop', True),
            auto_download=self.config['video'].get('auto_download', True)
        )
        
        self.preprocessor = Preprocessor(
            crop_top=self.config['preprocessing']['crop_top'],
            crop_left=self.config['preprocessing']['crop_left'],
            crop_bottom=self.config['preprocessing']['crop_bottom'],
            crop_right=self.config['preprocessing']['crop_right'],
            image_size=self.config['model']['image_size'],
            batch_size=self.config['model']['batch_size']
        )
        
        # Pass batch_size so the inference engine can fix dynamic
        # batch dimensions for NPU compilation when needed.
        self.inference = InferenceEngine(
            model_path=self.config['model']['path'],
            batch_size=self.config['model']['batch_size'],
        )
        
        self.postprocessor = SignalPostprocessor(
            sampling_rate=self.config['postprocessing']['sampling_rate'],
            pulse_lowcut=self.config['postprocessing']['pulse_lowcut'],
            pulse_highcut=self.config['postprocessing']['pulse_highcut'],
            resp_lowcut=self.config['postprocessing']['resp_lowcut'],
            resp_highcut=self.config['postprocessing']['resp_highcut']
        )
        
        self.grpc_client = RPPGGRPCClient(
            aggregator_host=self.config['aggregator']['host'],
            aggregator_port=self.config['aggregator']['port'],
            device_id="rppg-001"
        )
        
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info("Shutting down...")
        self.running = False
    
    def vital_generator(self):
        """Generate vitals."""
        # Wait for /start signal from control API
        logger.info("Waiting for /start control signal before streaming...")
        while self.running and not is_streaming_enabled():
            time.sleep(0.5)

        if not self.running:
            return

        self.video.start_stream()
        logger.info("✓ Video stream started")
        
        batch_count = 0
        numeric_interval = self.config['streaming'].get('numeric_interval', 5)
        
        try:
            while self.running:
                # Handle dynamic /start and /stop control
                if not is_streaming_enabled():
                    logger.info("Streaming paused via /stop; waiting for /start...")
                    self.video.stop_stream()
                    while self.running and not is_streaming_enabled():
                        time.sleep(0.5)
                    if not self.running:
                        break
                    logger.info("Streaming resumed via /start")
                    self.video.start_stream()

                for _ in range(self.config['model']['batch_size']):
                    frame = self.video.get_frame()
                    if frame is None:
                        self.video.stop_stream()
                        time.sleep(1)
                        self.video.start_stream()
                        frame = self.video.get_frame()
                    if frame is not None:
                        self.preprocessor.add_frame(frame)
                
                if not self.preprocessor.has_batch():
                    continue
                
                diff_batch, app_batch = self.preprocessor.get_batch()
                raw_output = self.inference.infer(diff_batch, app_batch)
                
                pulse_waveform = self.postprocessor.process_signal(raw_output, kind="pulse")
                resp_waveform = self.postprocessor.process_signal(raw_output, kind="resp")
                
                hr = self.postprocessor.compute_hr_from_fft(pulse_waveform)
                rr = self.postprocessor.compute_rr_from_fft(resp_waveform)
                
                batch_count += 1
                logger.info(f"Batch {batch_count}: HR={hr:.1f} BPM, RR={rr:.1f} BrPM")
                
                yield self.grpc_client.create_waveform_vital("HEART_RATE", hr, pulse_waveform, "BPM", self.config['postprocessing']['sampling_rate'])
                yield self.grpc_client.create_waveform_vital("RESP_RATE", rr, resp_waveform, "BrPM", self.config['postprocessing']['sampling_rate'])
                
                if batch_count % numeric_interval == 0:
                    yield self.grpc_client.create_numeric_vital("HEART_RATE_AVG", hr, "BPM")
                    yield self.grpc_client.create_numeric_vital("RESP_RATE_AVG", rr, "BrPM")
                
                time.sleep(self.config['streaming'].get('update_interval', 1.0))
        finally:
            self.video.stop_stream()
    
    def run(self):
        """Run service."""
        try:
            self.grpc_client.stream_vitals(self.vital_generator())
        except KeyboardInterrupt:
            logger.info("Interrupted")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
        finally:
            self.grpc_client.close()


def main():
    # Start control server in background thread
    control_thread = threading.Thread(target=start_control_server, daemon=True)
    control_thread.start()
    control_port = os.getenv("RPPG_CONTROL_PORT", "8084")
    logger.info(f"RPPG control server started on port {control_port}")

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    service = RPPGService(config_path)
    service.run()
    return 0


if __name__ == "__main__":
        sys.exit(main())