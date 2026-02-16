"""
RPPG gRPC Client - Streams both waveform and numeric vitals.
"""

import grpc
import time
import logging
from typing import Generator
from google.protobuf.empty_pb2 import Empty

# Import from proto package (same as aggregator)
from proto.vital_pb2 import Vital
from proto.vital_pb2_grpc import VitalServiceStub

logger = logging.getLogger(__name__)


class RPPGGRPCClient:
    """gRPC client for RPPG vitals."""
    
    def __init__(self, aggregator_host: str = "localhost", aggregator_port: int = 50051, device_id: str = "rppg-001"):
        self.aggregator_address = f"{aggregator_host}:{aggregator_port}"
        self.device_id = device_id
        self.channel = None
        self.stub = None
        self._connect()
    
    def _connect(self):
        """Connect to aggregator."""
        self.channel = grpc.insecure_channel(self.aggregator_address)
        self.stub = VitalServiceStub(self.channel)
        grpc.channel_ready_future(self.channel).result(timeout=5)
        logger.info(f"✓ Connected to aggregator at {self.aggregator_address}")
    
    def create_waveform_vital(self, metric: str, value: float, waveform: list, unit: str = "BPM", waveform_frequency_hz: int = 30) -> Vital:
        """Create waveform vital."""
        return Vital(
            device_id=self.device_id,
            metric=metric,
            value=value,
            unit=unit,
            timestamp=int(time.time() * 1000),
            waveform=waveform,
            waveform_frequency_hz=int(waveform_frequency_hz)
        )
    
    def create_numeric_vital(self, metric: str, value: float, unit: str = "BPM") -> Vital:
        """Create numeric vital."""
        return Vital(
            device_id=self.device_id,
            metric=metric,
            value=value,
            unit=unit,
            timestamp=int(time.time() * 1000)
        )
    
    def stream_vitals(self, vital_generator: Generator[Vital, None, None]):
        """Stream vitals to aggregator."""
        logger.info("Starting vital stream...")
        self.stub.StreamVitals(vital_generator)
    
    def close(self):
        """Close connection."""
        if self.channel:
            self.channel.close()
