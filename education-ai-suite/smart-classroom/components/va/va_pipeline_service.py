import subprocess
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List, Generator
import psutil
import signal
from dataclasses import dataclass
from enum import Enum
import atexit
import json
import threading
from utils.config_loader import config
from utils.rtsp_recorder import (
    start_rtsp_recording,
    stop_rtsp_recording,
    is_rtsp_recording_running,
)
from utils.runtime_config_loader import RuntimeConfig

class PipelineName(Enum):
    """Enumeration of pipeline names"""

    FRONT = "front"  # Pipeline 1
    BACK = "back"  # Pipeline 2
    CONTENT = "content"  # Pipeline 3

@dataclass
class PipelineOptions:
    """Minimal configuration options for pipelines"""

    device: str = "NPU"  # CPU, GPU, or NPU
    output_dir: str = "outputs"  # Directory for metadata output files
    output_rtsp: str = "rtsp://127.0.0.1:8554"  # RTSP output URL
    threshold: float = 0.5  # Detection threshold for YOLO
    record: bool = False


class VideoAnalyticsPipelineService:
    """Service to manage video analytics pipelines"""

    def __init__(self):
        """
        Initialize VideoAnalyticsPipelineService
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Set plugin path
        self.plugin_path = Path(config.va_pipeline.plugin_path).resolve()

        # Set model paths
        self.model_base_dir = Path(config.models.va.models_base_path).resolve() / "va"
        self.models = {
            "yolov8m": "yolov8m-pose.xml",
            "yolov8s": "yolov8s-pose.xml",
            "resnet18": "resnet18.xml",
            "mobilenetv2": "mobilenetv2.xml",
            "reid": "person-reidentification-retail-0288.xml",
        }

        # Active pipelines
        self.pipelines: Dict[str, subprocess.Popen] = {}

        # Pipeline log files & handles
        self.pipeline_logs: Dict[str, Path] = {}
        self.pipeline_log_handles: Dict[str, object] = {}

        # Pipeline output files
        self.pipeline_output_files: Dict[str, List[Path]] = {}

        # Pipeline monitoring threads
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.monitor_stop_flags: Dict[str, threading.Event] = {}

        # Pipeline launch parameters for restart
        self.pipeline_params: Dict[str, Dict] = {}

        # Pipeline retry counts
        self.pipeline_retry_counts: Dict[str, int] = {}
        self.max_retries = 10

        # Pipeline error events for status reporting (consumed by monitor_pipeline_status)
        self.pipeline_errors: Dict[str, List[str]] = {}

        ps = getattr(config.va_pipeline, "pose_statistics", None)
        self.min_frames_for_transition = getattr(ps, "min_frames_for_transition", 3) if ps else 3
        self.min_frames_for_transition_unid = getattr(ps, "min_frames_for_transition_unid", 15) if ps else 15
        self.absence_threshold = getattr(ps, "absence_threshold", 90) if ps else 90
        self.min_stand_frames = getattr(ps, "min_stand_frames", 10) if ps else 10
        self.center_dist_threshold = getattr(ps, "center_dist_threshold", 0.1) if ps else 0.1
        self.unidentified_max = getattr(ps, "unidentified_max", 50) if ps else 50
        self.stale_unidentified_threshold = getattr(ps, "stale_unidentified_threshold", 30) if ps else 30

        # Register cleanup handler
        atexit.register(self._cleanup)

    def _setup_environment(self):
        """Setup GStreamer environment variables"""
        current_path = os.environ.get("GST_PLUGIN_PATH", "")
        os.environ["GST_PLUGIN_PATH"] = f"{self.plugin_path};{current_path}"
        os.environ["GST_DEBUG"] = (
            "GVA_common:2,gvaposturedetect:4,gvareid:4,gvaroifilter:4"
        )
        os.environ["GST_PLUGIN_FEATURE_RANK"] = "d3d11h264dec:max,d3d11h265dec:max"

    def _get_model_path(self, model_key: str) -> str:
        """Get full path to model"""
        return (self.model_base_dir / self.models[model_key]).as_posix()

    def _validate_file_with_discoverer(self, file_path: str) -> Optional[str]:
        """Validate a file source using gst-discoverer-1.0

        Args:
            file_path: Path to the file to validate

        Returns:
            None if the file is valid, error message string if invalid
        """
        try:
            result = subprocess.run(
                ["gst-discoverer-1.0.exe", file_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            combined_output = result.stdout + result.stderr
            if "An error was encountered while discovering the file" in combined_output:
                self.logger.error(
                    f"File validation failed for '{file_path}': {combined_output}"
                )
                return combined_output.strip()
            return None
        except FileNotFoundError:
            self.logger.error("gst-discoverer-1.0.exe not found")
            return "gst-discoverer-1.0.exe not found"
        except subprocess.TimeoutExpired:
            self.logger.error(f"File validation timed out for '{file_path}'")
            return "File validation timed out"
        except Exception as e:
            self.logger.error(f"File validation error: {e}")
            return f"File validation error: {e}"

    def _get_source_elements(self, source: str, input_type: str) -> List[str]:
        """Get source elements based on input type"""
        if input_type == "rtsp" and config.va_pipeline.rtsp_codec == "h264":
            return [
                "rtspsrc",
                f"location={source}",
                "protocols=tcp",
                "!",
                "rtph264depay",
                "wait-for-keyframe=true",
                "!",
                "h264parse",
                "!",
                "d3d11h264dec",
                "!",
            ]
        elif input_type == "rtsp" and config.va_pipeline.rtsp_codec == "h265":
            return [
                "rtspsrc",
                f"location={source}",
                "protocols=tcp",
                "!",
                "rtph265depay",
                "wait-for-keyframe=true",
                "!",
                "h265parse",
                "!",
                "d3d11h265dec",
                "!",
            ]
        elif input_type == "file":
            return [
                "filesrc",
                f"location={Path(source).as_posix()}",
                "!",
                "decodebin3",
                "!",
            ]
        else:
            raise ValueError(f"Unknown input type: {input_type}")

    def _get_rtsp_sink_elements(self, rtsp_url: str, pipeline_name: str) -> List[str]:
        """Get RTSP sink elements for pushing to RTSP server"""
        return [
            "mfh264enc",
            "bitrate=2000",
            "gop-size=15",
            "!",
            "h264parse",
            "!",
            "queue",
            "!",
            "rtspclientsink",
            f"location={rtsp_url}/{pipeline_name}",
            "protocols=udp",
        ]

    def _check_redistribute_latency(self, log_file: Path) -> bool:
        """Check if 'Redistribute latency' appears in log file"""
        try:
            with open(log_file, "r") as f:
                content = f.read()
                return "Redistribute latency" in content
        except Exception as e:
            self.logger.warning(f"Failed to check log file: {e}")
            return False

    def _check_error(self, log_file: Path) -> Optional[str]:
        """Check if 'ERROR' appears in log file and return error text.

        Returns:
            The error text from 'ERROR: from element' to end of file,
            or None if no error found.
        """
        try:
            with open(log_file, "r") as f:
                content = f.read()
                idx = content.find("ERROR: from element")
                if idx >= 0:
                    return content[idx:].strip()
                return None
        except Exception as e:
            self.logger.warning(f"Failed to check log file: {e}")
            return None

    def _check_normal_exit(self, log_file: Path) -> bool:
        """Check if pipeline exited normally (has EOS message)"""
        try:
            with open(log_file, "r") as f:
                content = f.read()
                return 'Got EOS from element "pipeline0".' in content
        except Exception as e:
            self.logger.warning(f"Failed to check log file: {e}")
            return False

    def _monitor_pipeline(self, pipeline_name: str):
        """
        Monitor pipeline process and restart if it exits unexpectedly

        Args:
            pipeline_name: Name of the pipeline to monitor
        """
        stop_flag = self.monitor_stop_flags[pipeline_name]

        while not stop_flag.is_set():
            # Check if pipeline process is still running
            if pipeline_name not in self.pipelines:
                break

            process = self.pipelines[pipeline_name]

            # Check process status
            if process.poll() is not None:
                # Process has exited
                log_file = self.pipeline_logs.get(pipeline_name)

                if log_file and self._check_normal_exit(log_file):
                    # Normal exit with EOS
                    self.logger.info(
                        f"Pipeline '{pipeline_name}' exited normally (EOS received)"
                    )
                    break
                else:
                    # Unexpected exit — record error for status reporting
                    log_error = self._check_error(log_file) if log_file else None
                    error_detail = log_error or f"Pipeline exited with code {process.returncode}"
                    if pipeline_name not in self.pipeline_errors:
                        self.pipeline_errors[pipeline_name] = []
                    self.pipeline_errors[pipeline_name].append(error_detail)
                    self.logger.warning(
                        f"Pipeline '{pipeline_name}' exited unexpectedly: {error_detail}"
                    )

                    retry_count = self.pipeline_retry_counts.get(pipeline_name, 0)

                    if retry_count < self.max_retries:
                        self.logger.warning(
                            f"Pipeline '{pipeline_name}' exited unexpectedly. "
                            f"Restarting... (attempt {retry_count + 1}/{self.max_retries})"
                        )

                        # Increment retry count
                        self.pipeline_retry_counts[pipeline_name] = retry_count + 1

                        # Close old log handle
                        if pipeline_name in self.pipeline_log_handles:
                            try:
                                self.pipeline_log_handles[pipeline_name].close()
                            except:
                                pass

                        # Restart pipeline using saved parameters
                        params = self.pipeline_params.get(pipeline_name)
                        if params:
                            self._launch_pipeline_internal(
                                pipeline_name, params["options"], params["command"]
                            )
                        else:
                            self.logger.error(
                                f"Cannot restart pipeline '{pipeline_name}': parameters not found"
                            )
                            break
                    else:
                        self.logger.error(
                            f"Pipeline '{pipeline_name}' reached maximum retry limit ({self.max_retries}). "
                            f"Giving up."
                        )
                        break

            # Check every 2 seconds
            time.sleep(2)

        self.logger.info(f"Monitor thread for pipeline '{pipeline_name}' stopped")

    def _launch_pipeline_internal(
        self, pipeline_name: str, options: PipelineOptions, command: List[str]
    ) -> bool:
        """
        Internal method to launch pipeline (used for initial launch and restarts)

        Args:
            pipeline_name: Name of pipeline
            options: Pipeline options
            command: Full command to execute

        Returns:
            True if pipeline launched successfully, False otherwise
        """
        try:
            # Create log file for pipeline output
            log_dir = Path(options.output_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"{pipeline_name}_{int(time.time())}.log"
            log_handle = open(log_file, "w", buffering=1)  # Line buffered

            # Launch pipeline
            process = subprocess.Popen(
                command,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=os.environ.copy(),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )

            # Store pipeline process, log file, and log handle
            self.pipelines[pipeline_name] = process
            self.pipeline_logs[pipeline_name] = log_file
            self.pipeline_log_handles[pipeline_name] = log_handle

            self.logger.info(
                f"Pipeline '{pipeline_name}' started with PID: {process.pid}"
            )
            self.logger.info(f"  Log file: {log_file}")

            # Check for "Redistribute latency" in log file
            time.sleep(5)
            self.pipeline_log_handles[pipeline_name].flush()
            if self._check_redistribute_latency(log_file):
                self.logger.info("Pipeline initialized successfully")
            else:
                self.logger.warning("Pipeline may not have initialized properly")
            error_text = self._check_error(log_file)
            if error_text:
                self.logger.error(f"Errors detected in pipeline log:\n{error_text}")
                raise RuntimeError(error_text)

            return True

        except RuntimeError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to launch pipeline '{pipeline_name}': {e}")
            return False

    def _build_pipeline_front(
        self, source: str, options: PipelineOptions, input_type: str
    ) -> List[str]:
        """Build front camera pipeline (Pipeline 1)"""
        output_dir = Path(options.output_dir)
        output_dir.mkdir(exist_ok=True)

        pipeline = [
            *self._get_source_elements(source, input_type),
            # YOLO detection
            "gvadetect",
            f"model={self._get_model_path('yolov8m')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "model-instance-id=yolo-0",
            f"threshold={options.threshold}",
            "inference-region=0",
            "!",
            "gvaposturedetect",
            "!",
            "tee",
            "name=t",
            # Branch 1: ResNet18 classification
            "t.",
            "!",
            "queue",
            "!",
            "gvaroifilter",
            "max-rois-num=10",
            "!",
            "gvaclassify",
            f"model={self._get_model_path('resnet18')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "inference-region=1",
            "model-instance-id=resnet18-0",
            "!",
            "gvafpscounter",
            "!",
            "gvametaconvert",
            "!",
            "gvametapublish",
            f"file-path={output_dir.as_posix()}/front_resnet18.txt",
            "file-format=json-lines",
            "!",
            "fakesink",
            "async=false",
            "sync=false",
            # Branch 2: ReID and RTSP output
            "t.",
            "!",
            "queue",
            "!",
            "gvaroifilter",
            "max-rois-num=2",
            "label=stand,stand_raise_up",
            "!",
            "gvaclassify",
            f"model={self._get_model_path('reid')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "inference-region=1",
            "model-instance-id=resnest50-0",
            "!",
            "queue",
            "!",
            "gvareid",
            "similarity-threshold=0.6",
            "!",
            "gvaroifilter",
            "!",
            "gvafpscounter",
            "!",
            "gvametaconvert",
            "!",
            "gvametapublish",
            f"file-path={output_dir.as_posix()}/front_posture.txt",
            "file-format=json-lines",
            "!",
            "gvawatermark",
            "!",
            *self._get_rtsp_sink_elements(options.output_rtsp, "front_stream"),
            # Branch 3: MobileNetv2 classification
            "t.",
            "!",
            "queue",
            "!",
            "gvaroifilter",
            "max-rois-num=50",
            "!",
            "gvaclassify",
            f"model={self._get_model_path('mobilenetv2')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "inference-region=1",
            "model-instance-id=mobilenetv2-0",
            "!",
            "gvafpscounter",
            "!",
            "gvametaconvert",
            "!",
            "gvametapublish",
            f"file-path={output_dir.as_posix()}/front_mobilenetv2.txt",
            "file-format=json-lines",
            "!",
            "fakesink",
            "async=false",
            "sync=false",
        ]
        return pipeline

    def _build_pipeline_back(
        self, source: str, options: PipelineOptions, input_type: str
    ) -> List[str]:
        """Build back camera pipeline (Pipeline 2)"""
        output_dir = Path(options.output_dir)
        output_dir.mkdir(exist_ok=True)

        pipeline = [
            *self._get_source_elements(source, input_type),
            # YOLO detection
            "gvadetect",
            f"model={self._get_model_path('yolov8s')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "model-instance-id=yolo-0",
            f"threshold={options.threshold}",
            "inference-region=0",
            "!",
            "gvaposturedetect",
            "!",
            "gvawatermark",
            "!",
            "gvametaconvert",
            "!",
            "gvametapublish",
            f"file-path={output_dir.as_posix()}/back_posture.txt",
            "file-format=json-lines",
            "!",
            "queue",
            "!",
            # ResNet18 classification
            "gvaclassify",
            f"model={self._get_model_path('resnet18')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "inference-region=1",
            "model-instance-id=resnet18-0",
            "!",
            "gvafpscounter",
            "!",
            "gvametaconvert",
            "!",
            "gvametapublish",
            f"file-path={output_dir.as_posix()}/back_resnet18.txt",
            "file-format=json-lines",
            "!",
            *self._get_rtsp_sink_elements(options.output_rtsp, "back_stream"),
        ]
        return pipeline

    def _build_pipeline_content(
        self, source: str, options: PipelineOptions, input_type: str
    ) -> List[str]:
        """Build content/file pipeline (Pipeline 3)"""
        output_dir = Path(options.output_dir)
        output_dir.mkdir(exist_ok=True)

        pipeline = [
            *self._get_source_elements(source, input_type),
            # Branch 1: ResNet18 classification
            "videorate",
            "!",
            "video/x-raw(memory:D3D11Memory),framerate=1/1",
            "!",
            "gvaclassify",
            f"model={self._get_model_path('resnet18')}",
            f"device={options.device}",
            "pre-process-backend=d3d11",
            "batch-size=1",
            "inference-region=0",
            "model-instance-id=resnet18-0",
            "!",
            "gvafpscounter",
            "!",
            "gvametaconvert",
            "!",
            "gvametapublish",
            f"file-path={output_dir.as_posix()}/content_results.txt",
            "file-format=json-lines",
            "!",
            "gvawatermark",
            "!",
            *self._get_rtsp_sink_elements(options.output_rtsp, "content_stream"),
        ]
        return pipeline

    def launch_pipeline(
        self, pipeline_name: str, source: str, options: Optional[PipelineOptions] = None
    ) -> bool:
        """
        Launch a pipeline by name

        Args:
            pipeline_name: Name of pipeline ('front', 'back', or 'content')
            source: Input source (RTSP URL or file path)
            options: Optional pipeline configuration options

        Returns:
            True if pipeline launched successfully, False otherwise

        Note:
            - Source can be RTSP URL (rtsp://...) or local file path
            - Input type is auto-detected from source (starts with 'rtsp://' = RTSP, else file)
            - Video output is always pushed to RTSP server (configured via options.output_rtsp)
            - Metadata is saved to files in options.output_dir
        """
        # Validate pipeline name
        valid_names = [p.value for p in PipelineName]
        if pipeline_name not in valid_names:
            self.logger.error(
                f"Invalid pipeline name: {pipeline_name}. Valid names: {valid_names}"
            )
            return False

        # Check if pipeline is already running
        if pipeline_name in self.pipelines and self.is_pipeline_running(pipeline_name):
            self.logger.warning(f"Pipeline '{pipeline_name}' is already running")
            return False

        # Use default options if not provided
        if options is None:
            options = PipelineOptions()

        # Auto-detect input type from source
        if source.startswith("rtsp://"):
            input_type = "rtsp"
        else:
            input_type = "file"
            # Verify file exists
            if not Path(source).exists():
                self.logger.error(f"Source file not found: {source}")
                raise ValueError(f"Source file not found: {source}")
            # Validate file with gst-discoverer
            error_msg = self._validate_file_with_discoverer(source)
            if error_msg:
                raise ValueError(f"Invalid source file '{source}': {error_msg}")

        try:
            # Setup environment
            self._setup_environment()

            # Build pipeline based on name
            if pipeline_name == PipelineName.FRONT.value:
                pipeline_elements = self._build_pipeline_front(
                    source, options, input_type
                )
            elif pipeline_name == PipelineName.BACK.value:
                pipeline_elements = self._build_pipeline_back(
                    source, options, input_type
                )
            elif pipeline_name == PipelineName.CONTENT.value:
                pipeline_elements = self._build_pipeline_content(
                    source, options, input_type
                )
            else:
                raise ValueError(f"Unknown pipeline: {pipeline_name}")

            # Build full command
            command = ["gst-launch-1.0.exe", "-e"] + pipeline_elements

            self.logger.info(f"Launching pipeline '{pipeline_name}'")
            self.logger.info(f"  Source: {source} (type: {input_type})")
            self.logger.info(f"  RTSP output: {options.output_rtsp}")
            self.logger.info(f"  Metadata dir: {options.output_dir}")
            self.logger.info(f"Command: {' '.join(command)}")

            # Store output files for monitoring
            output_files = []
            if pipeline_name == PipelineName.FRONT.value:
                output_files = [
                    Path(options.output_dir) / "front_resnet18.txt",
                    Path(options.output_dir) / "front_posture.txt",
                    Path(options.output_dir) / "front_mobilenetv2.txt",
                ]
            elif pipeline_name == PipelineName.BACK.value:
                output_files = [
                    Path(options.output_dir) / "back_posture.txt",
                    Path(options.output_dir) / "back_resnet18.txt",
                ]
            elif pipeline_name == PipelineName.CONTENT.value:
                output_files = [Path(options.output_dir) / "content_results.txt"]
            self.pipeline_output_files[pipeline_name] = output_files

            # Save pipeline parameters for restart capability
            self.pipeline_params[pipeline_name] = {
                "options": options,
                "command": command,
            }

            # Initialize retry count
            self.pipeline_retry_counts[pipeline_name] = 0

            # Launch pipeline
            success = self._launch_pipeline_internal(pipeline_name, options, command)

            if not success:
                return False

            # ---- START RTSP RECORDING ----
            if options.record:
                recorder_name = f"{pipeline_name}_recorder"

                project_config = RuntimeConfig.get_section("Project")
                output_video_path = os.path.join(
                    project_config.get("location"),
                    project_config.get("name"),
                    self.x_session_id,
                    f"{pipeline_name}.mp4"
                )

                start_rtsp_recording(
                    name=recorder_name,
                    rtsp_url=source,
                    output_file=output_video_path,
                )

            # Start monitoring thread
            stop_flag = threading.Event()
            self.monitor_stop_flags[pipeline_name] = stop_flag

            monitor_thread = threading.Thread(
                target=self._monitor_pipeline,
                args=(pipeline_name,),
                daemon=True,
                name=f"monitor-{pipeline_name}",
            )
            monitor_thread.start()
            self.monitor_threads[pipeline_name] = monitor_thread

            self.logger.info(
                f"Started monitoring thread for pipeline '{pipeline_name}'"
            )

            return True

        except RuntimeError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to launch pipeline '{pipeline_name}': {e}")
            return False

    def stop_pipeline(self, pipeline_name: str, timeout: float = 10.0) -> bool:
        """
        Stop a running pipeline

        Args:
            pipeline_name: Name of pipeline to stop
            timeout: Maximum time to wait for graceful shutdown (seconds)

        Returns:
            True if pipeline stopped successfully, False otherwise
        """
        pipeline_name = pipeline_name.lower()

        if pipeline_name not in self.pipelines:
            self.logger.warning(f"Pipeline '{pipeline_name}' is not registered")
            return False

        stop_rtsp_recording(f"{pipeline_name}_recorder")
        process = self.pipelines[pipeline_name]

        if process.poll() is not None:
            self.logger.info(f"Pipeline '{pipeline_name}' is not running")
            del self.pipelines[pipeline_name]
            return True

        try:
            self.logger.info(
                f"Stopping pipeline '{pipeline_name}' (PID: {process.pid})"
            )

            # Try graceful shutdown
            if sys.platform == "win32":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()

            # Wait for process to terminate
            try:
                process.wait(timeout=timeout)
                self.logger.info(f"Pipeline '{pipeline_name}' stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning(
                    f"Pipeline did not stop within {timeout}s, forcing kill..."
                )
                process.kill()
                process.wait(timeout=5)
                self.logger.info(f"Pipeline '{pipeline_name}' killed")

            del self.pipelines[pipeline_name]

            # Stop monitoring thread
            if pipeline_name in self.monitor_stop_flags:
                self.monitor_stop_flags[pipeline_name].set()

            if pipeline_name in self.monitor_threads:
                monitor_thread = self.monitor_threads[pipeline_name]
                monitor_thread.join(timeout=2.0)
                del self.monitor_threads[pipeline_name]

            # Clean up associated data
            if pipeline_name in self.pipeline_logs:
                del self.pipeline_logs[pipeline_name]
            if pipeline_name in self.pipeline_log_handles:
                # Close the log file handle
                try:
                    self.pipeline_log_handles[pipeline_name].close()
                except:
                    pass
                del self.pipeline_log_handles[pipeline_name]
            if pipeline_name in self.pipeline_output_files:
                del self.pipeline_output_files[pipeline_name]
            if pipeline_name in self.pipeline_params:
                del self.pipeline_params[pipeline_name]
            if pipeline_name in self.pipeline_retry_counts:
                del self.pipeline_retry_counts[pipeline_name]
            if pipeline_name in self.monitor_stop_flags:
                del self.monitor_stop_flags[pipeline_name]
            if pipeline_name in self.pipeline_errors:
                del self.pipeline_errors[pipeline_name]

            return True

        except Exception as e:
            self.logger.error(f"Error stopping pipeline '{pipeline_name}': {e}")
            return False

    def is_pipeline_running(self, pipeline_name: str) -> bool:
        """Check if a pipeline is currently running"""
        pipeline_name = pipeline_name.lower()

        if pipeline_name not in self.pipelines:
            return False

        process = self.pipelines[pipeline_name]
        return process.poll() is None

    async def monitor_pipeline_status(
        self, check_interval: float = 2.0
    ):
        """
        Monitor all pipeline processes status and yield status updates for streaming response

        This async generator continuously monitors all pipeline process states and yields
        combined status information. It does NOT restart the pipelines - that is handled by
        the internal _monitor_pipeline thread.

        Args:
            check_interval: Seconds between status checks (default: 2.0)

        Yields:
            Dictionary with status information for all pipelines:
            - pipelines: List of pipeline status dictionaries, each containing:
                - pipeline_name: Name of the pipeline
                - status: 'running', 'stopped_normal', 'stopped_error', or 'not_found'
                - pid: Process ID (if running)
                - message: Additional status message
                - error: Error details (if stopped with error)

        Note:
            This is designed for streaming responses. The _monitor_pipeline thread
            handles automatic restarts, so this function only reports status.
        """
        import asyncio

        all_pipeline_names = ["front", "back", "content"]
        self.logger.info(f"Starting status monitoring for all pipelines: {all_pipeline_names}")

        try:
            while True:
                pipeline_statuses = []
                all_stopped = True

                for pipeline_name in all_pipeline_names:
                    pipeline_name_lower = pipeline_name.lower()

                    # Check if pipeline is registered
                    if pipeline_name_lower not in self.pipelines:
                        pipeline_statuses.append({
                            "pipeline_name": pipeline_name,
                            "status": "not_found",
                            "message": f"Pipeline '{pipeline_name}' not found",
                        })
                        continue

                    process = self.pipelines[pipeline_name_lower]
                    return_code = process.poll()

                    # Collect any error events recorded by the monitor thread
                    errors = self.pipeline_errors.pop(pipeline_name_lower, [])

                    # Pipeline is running
                    if return_code is None:
                        all_stopped = False
                        status_entry = {
                            "pipeline_name": pipeline_name,
                            "status": "running",
                            "pid": process.pid,
                        }
                        if errors:
                            status_entry["errors"] = errors
                        pipeline_statuses.append(status_entry)

                    # Pipeline has stopped
                    else:
                        log_file = self.pipeline_logs.get(pipeline_name_lower)

                        # Check if it was a normal exit
                        if log_file and self._check_normal_exit(log_file):
                            pipeline_statuses.append({
                                "pipeline_name": pipeline_name,
                                "status": "stopped_normal",
                                "return_code": return_code,
                                "message": "Pipeline exited normally (EOS received)",
                            })
                        else:
                            if not errors:
                                log_error = self._check_error(log_file) if log_file else None
                                if log_error:
                                    errors = [log_error]

                            pipeline_statuses.append({
                                "pipeline_name": pipeline_name,
                                "status": "stopped_error",
                                "return_code": return_code,
                                "message": "Pipeline exited unexpectedly.",
                                "errors": errors,
                            })

                # Yield combined status
                yield {"pipelines": pipeline_statuses}

                await asyncio.sleep(check_interval)

        except Exception as e:
            self.logger.error(f"Error monitoring pipeline status: {e}")
            yield {
                "pipeline_name": pipeline_name,
                "status": "error",
                "error": str(e),
                "message": "Monitoring error occurred",
            }

    def monitor_pipeline_result(
        self, pipeline_name: str, file_name: Optional[str] = None
    ) -> Generator[Dict, None, None]:
        """
        Monitor pipeline output file and yield JSON objects as new lines are written

        Args:
            pipeline_name: Name of pipeline to monitor
            file_name: Specific output file to monitor (e.g., "front_resnet18.txt")
                      If None, monitors the first output file for the pipeline

        Yields:
            Dictionary parsed from each new JSON line in the output file

        Note:
            This is a blocking generator that continuously monitors the file.
            Use Ctrl+C or call stop_pipeline() to stop monitoring.
        """
        pipeline_name = pipeline_name.lower()

        if pipeline_name not in self.pipelines:
            self.logger.error(f"Pipeline '{pipeline_name}' is not registered")
            return

        if pipeline_name not in self.pipeline_output_files:
            self.logger.error(
                f"No output files registered for pipeline '{pipeline_name}'"
            )
            return

        # Determine which file to monitor
        output_files = self.pipeline_output_files[pipeline_name]
        if not output_files:
            self.logger.error(f"No output files found for pipeline '{pipeline_name}'")
            return

        if file_name:
            # Find the matching file
            target_file = None
            for f in output_files:
                if f.name == file_name or str(f) == file_name:
                    target_file = f
                    break
            if not target_file:
                self.logger.error(
                    f"File '{file_name}' not found in pipeline output files: {[str(f) for f in output_files]}"
                )
                return
        else:
            # Use the first file
            target_file = output_files[0]

        self.logger.info(f"Monitoring file: {target_file}")

        # Wait for file to be created
        timeout = 30
        start_time = time.time()
        while not target_file.exists():
            if time.time() - start_time > timeout:
                self.logger.error(f"Timeout waiting for file: {target_file}")
                return
            if not self.is_pipeline_running(pipeline_name):
                self.logger.error(
                    f"Pipeline stopped before file was created: {target_file}"
                )
                return
            time.sleep(0.5)

        # Monitor the file for new lines
        try:
            with open(target_file, "r") as f:
                # Seek to the end of existing content
                f.seek(0, 2)

                while self.is_pipeline_running(pipeline_name):
                    line = f.readline()
                    if line:
                        line = line.strip()
                        if line:
                            try:
                                # Parse JSON and yield
                                json_obj = json.loads(line)
                                yield json_obj
                            except json.JSONDecodeError as e:
                                self.logger.warning(f"Failed to parse JSON line: {e}")
                                self.logger.debug(f"Line content: {line}")
                    else:
                        # No new data, wait a bit
                        time.sleep(0.1)

                self.logger.info(
                    f"Pipeline '{pipeline_name}' stopped, ending monitoring"
                )

        except Exception as e:
            self.logger.error(f"Error monitoring file: {e}")
            return

    def get_pipeline_status(self, pipeline_name: str) -> Optional[Dict]:
        """
        Get status information for a pipeline (non-blocking)

        Args:
            pipeline_name: Name of pipeline to check

        Returns:
            Dictionary with pipeline status information, or None if not found
        """
        pipeline_name = pipeline_name.lower()

        if pipeline_name not in self.pipelines:
            return None

        process = self.pipelines[pipeline_name]

        status = {
            "name": pipeline_name,
            "running": process.poll() is None,
            "pid": process.pid,
            "return_code": process.poll(),
        }

        # Add process details if running
        if status["running"]:
            try:
                proc = psutil.Process(process.pid)
                status["cpu_percent"] = proc.cpu_percent()
                status["memory_mb"] = proc.memory_info().rss / 1024 / 1024
                status["uptime_seconds"] = time.time() - proc.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Add log file info
        if pipeline_name in self.pipeline_logs:
            status["log_file"] = str(self.pipeline_logs[pipeline_name])

        # Add output files info
        if pipeline_name in self.pipeline_output_files:
            status["output_files"] = [
                str(f) for f in self.pipeline_output_files[pipeline_name]
            ]

        return status

    def get_all_pipelines_status(self) -> Dict[str, Dict]:
        """Get status of all registered pipelines (non-blocking)"""
        return {name: self.get_pipeline_status(name) for name in self.pipelines.keys()}

    def stop_all_pipelines(self, timeout: float = 10.0) -> bool:
        """Stop all running pipelines"""
        self.logger.info("Stopping all pipelines...")
        success = True

        for pipeline_name in list(self.pipelines.keys()):
            if not self.stop_pipeline(pipeline_name, timeout):
                success = False

        return success

    def _cleanup(self):
        """Cleanup handler called on process exit"""
        if self.pipelines:
            self.logger.info("Cleaning up pipelines on exit...")

            # Stop all monitoring threads first
            for stop_flag in self.monitor_stop_flags.values():
                stop_flag.set()

            # Wait for monitoring threads to finish
            for thread in self.monitor_threads.values():
                thread.join(timeout=2.0)

            self.stop_all_pipelines(timeout=5.0)

            # Close any remaining log file handles
            for handle in self.pipeline_log_handles.values():
                try:
                    handle.close()
                except:
                    pass
            self.pipeline_log_handles.clear()

    def get_pose_stats(
        self, front_posture_file: str, previous_state: Optional[Dict] = None
    ) -> tuple[Dict, Dict]:
        """
        Incrementally analyze front_posture.txt and generate pose statistics
        Only processes new lines since last call, reusing previous results
        
        Args:
            front_posture_file: Path to front_posture.txt file
            previous_state: State from previous call (contains processed_lines, 
            frames, counters, etc.)
            
        Returns:
            Tuple of (statistics_dict, new_state_dict):
            - statistics: Current statistics with all data up to now
                - student_count: Average person count
                - stand_count: Count of stand transitions
                - raise_up_count: Count of raise up transitions
                - stand_reid: List of student IDs with their stand transition counts
            - state: State to pass to next call for incremental processing
        """
        posture_file = Path(front_posture_file)

        # Initialize state if first call
        if previous_state is None:
            previous_state = {
                "processed_lines": 0,
                "total_frames": 0,
                "person_count_samples": [],  # person counts sampled at target frame indices
                "last_person_count": 0,       # person count from the most recent frame
                "student_states": {},
                "student_stand_counts": {},
                "student_raise_counts": {},
                "unidentified_objects": [],
                "total_raise_count_no_id": 0,
            }

        if not posture_file.exists():
            return {
                "student_count": 0,
                "stand_count": 0,
                "raise_up_count": 0,
                "stand_reid": [],
            }, previous_state

        try:
            with open(posture_file, "r") as f:
                all_lines = f.readlines()

            processed_lines = previous_state["processed_lines"]
            new_lines = all_lines[processed_lines:]

            if not new_lines:
                return self._calculate_stats(previous_state), previous_state

            # Process frames directly — do not accumulate them in memory
            TARGET_FRAMES = {900, 1800, 2700}
            frame_base = previous_state["total_frames"]
            new_frames = 0

            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    frame = json.loads(line)
                except json.JSONDecodeError:
                    continue

                frame_idx = frame_base + new_frames
                new_frames += 1

                objects = frame.get("objects", [])
                valid_objects = [
                    obj for obj in objects
                    if obj.get("detection", {}).get("bounding_box", {}).get("x_max", 0) > 0
                ]

                # Sample person count only at target frame indices
                if frame_idx in TARGET_FRAMES:
                    previous_state["person_count_samples"].append(len(valid_objects))
                previous_state["last_person_count"] = len(valid_objects)

                self._process_frame(frame_idx, valid_objects, previous_state)

            previous_state["processed_lines"] = len(all_lines)
            previous_state["total_frames"] = frame_base + new_frames

            return self._calculate_stats(previous_state), previous_state

        except Exception as e:
            self.logger.error(f"Error in incremental pose statistics: {e}")
            return {
                "student_count": 0,
                "stand_count": 0,
                "raise_up_count": 0,
                "stand_reid": [],
            }, previous_state

    def _process_frame(self, frame_idx: int, valid_objects: List, state: Dict):
        """Process a single frame, updating tracking state in-place.

        Improvements vs original _process_frames_incremental:
        - ABSENCE_THRESHOLD raised 15 → 90 frames (~3s) to suppress ReID tracking noise
        - MIN_STAND_FRAMES=10: stand counted only after ID persists ≥10 consecutive frames
          (filters 81.7% of noise: ghost 1-2f=66% + very-short 3-5f=15.7%)
        - Re-entry while already raising immediately counts as a raise event (no missed raises)
        - Unidentified objects matched by bbox center distance instead of IoU (faster, more robust)
        - unidentified_objects list capped at 50 entries to bound O(N) scan cost
        """
        MIN_FRAMES_FOR_TRANSITION = self.min_frames_for_transition
        MIN_FRAMES_FOR_TRANSITION_UNID = self.min_frames_for_transition_unid
        ABSENCE_THRESHOLD = self.absence_threshold
        MIN_STAND_FRAMES = self.min_stand_frames
        CENTER_DIST_THRESHOLD = self.center_dist_threshold
        UNIDENTIFIED_MAX = self.unidentified_max

        student_states = state["student_states"]
        student_stand_counts = state["student_stand_counts"]
        student_raise_counts = state["student_raise_counts"]
        unidentified_objects = state["unidentified_objects"]

        seen_student_ids = set()
        matched_unidentified = set()

        for obj in valid_objects:
            detection = obj.get("detection", {})
            label = detection.get("label", "")
            student_id = obj.get("id", 0)
            bbox = detection.get("bounding_box", {})

            is_raising = label in ["sit_raise_up", "stand_raise_up"]

            if student_id > 0:
                seen_student_ids.add(student_id)

                if student_id not in student_states:
                    # First appearance — start confirmation window, don't count stand yet
                    if student_id not in student_raise_counts:
                        student_raise_counts[student_id] = 0
                    # If reappearing while already raising, count it immediately
                    if is_raising:
                        student_raise_counts[student_id] += 1
                    student_states[student_id] = {
                        "last_seen_frame": frame_idx,
                        "is_raising": is_raising,
                        "raise_buffer": 0,
                        "continuous_frames": 1,
                        "stand_confirmed": False,
                    }
                else:
                    st = student_states[student_id]
                    st["last_seen_frame"] = frame_idx
                    st["continuous_frames"] += 1

                    # Confirm stand once ID has persisted MIN_STAND_FRAMES consecutive frames
                    if not st["stand_confirmed"] and st["continuous_frames"] >= MIN_STAND_FRAMES:
                        student_stand_counts[student_id] = student_stand_counts.get(student_id, 0) + 1
                        st["stand_confirmed"] = True

                    if is_raising != st["is_raising"]:
                        st["raise_buffer"] += 1
                        if st["raise_buffer"] >= MIN_FRAMES_FOR_TRANSITION:
                            if is_raising:
                                student_raise_counts[student_id] += 1
                            st["is_raising"] = is_raising
                            st["raise_buffer"] = 0
                    else:
                        st["raise_buffer"] = 0

            else:
                # Unidentified object: match by bbox center distance
                cx = (bbox.get("x_min", 0) + bbox.get("x_max", 0)) / 2
                cy = (bbox.get("y_min", 0) + bbox.get("y_max", 0)) / 2

                best_match_idx = -1
                best_dist = CENTER_DIST_THRESHOLD

                for idx, unid_obj in enumerate(unidentified_objects):
                    if idx in matched_unidentified:
                        continue
                    ux, uy = unid_obj["center"]
                    dist = ((cx - ux) ** 2 + (cy - uy) ** 2) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_match_idx = idx

                if best_match_idx >= 0:
                    unid_obj = unidentified_objects[best_match_idx]
                    matched_unidentified.add(best_match_idx)
                    unid_obj["center"] = (cx, cy)

                    if is_raising != unid_obj["is_raising"]:
                        unid_obj["raise_buffer"] += 1
                        if unid_obj["raise_buffer"] >= MIN_FRAMES_FOR_TRANSITION_UNID:
                            if is_raising:
                                unid_obj["raise_count"] += 1
                                state["total_raise_count_no_id"] += 1
                            unid_obj["is_raising"] = is_raising
                            unid_obj["raise_buffer"] = 0
                    else:
                        unid_obj["raise_buffer"] = 0

                    unid_obj["last_seen_frame"] = frame_idx
                elif len(unidentified_objects) < UNIDENTIFIED_MAX:
                    unidentified_objects.append({
                        "center": (cx, cy),
                        "is_raising": is_raising,
                        "raise_buffer": 0,
                        "raise_count": 0,
                        "last_seen_frame": frame_idx,
                    })

        # Remove stale unidentified objects
        state["unidentified_objects"] = [
            obj for obj in unidentified_objects
            if frame_idx - obj["last_seen_frame"] < self.stale_unidentified_threshold
        ]

        # Remove students absent too long — re-appearance will count as a new stand-up
        for student_id in list(student_states.keys()):
            if student_id not in seen_student_ids:
                if frame_idx - student_states[student_id]["last_seen_frame"] >= ABSENCE_THRESHOLD:
                    del student_states[student_id]

    def _calculate_stats(self, state: Dict) -> Dict:
        """Calculate current statistics from accumulated state."""
        if state["total_frames"] == 0:
            return {
                "student_count": 0,
                "stand_count": 0,
                "raise_up_count": 0,
                "stand_reid": [],
            }

        person_count_samples = state["person_count_samples"]
        if person_count_samples:
            student_count = int(sum(person_count_samples) / len(person_count_samples))
        else:
            student_count = state["last_person_count"]

        stand_count = sum(state["student_stand_counts"].values())
        raise_up_count = (
            sum(state["student_raise_counts"].values()) + state["total_raise_count_no_id"]
        )
        stand_reid = [
            {"student_id": sid, "count": cnt}
            for sid, cnt in sorted(state["student_stand_counts"].items())
            if cnt > 0
        ]

        return {
            "student_count": student_count,
            "stand_count": stand_count,
            "raise_up_count": raise_up_count,
            "stand_reid": stand_reid,
        }
