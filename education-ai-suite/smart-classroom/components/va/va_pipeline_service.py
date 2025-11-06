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
from utils.config_loader import config


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

        # Register cleanup handler
        atexit.register(self._cleanup)

    def _setup_environment(self):
        """Setup GStreamer environment variables"""
        current_path = os.environ.get("GST_PLUGIN_PATH", "")
        os.environ["GST_PLUGIN_PATH"] = f"{self.plugin_path};{current_path}"
        os.environ["GST_DEBUG"] = "GVA_common:2,gvaposturedetect:4,gvareid:4,gvaroifilter:4"

    def _get_model_path(self, model_key: str) -> str:
        """Get full path to model"""
        return (self.model_base_dir / self.models[model_key]).as_posix()

    def _get_source_elements(self, source: str, input_type: str) -> List[str]:
        """Get source elements based on input type"""
        if input_type == "rtsp":
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
        elif input_type == "file":
            return [
                "filesrc",
                f"location={source}",
                "!",
                "qtdemux",
                "!",
                "h264parse",
                "!",
                "d3d11h264dec",
                "!",
            ]
        else:
            raise ValueError(f"Unknown input type: {input_type}")

    def _get_rtsp_sink_elements(
        self, rtsp_url: str, pipeline_name: str
    ) -> List[str]:
        """Get RTSP sink elements for pushing to RTSP server"""
        return [
            "mfh264enc",
            "bitrate=5000",
            "gop-size=15",
            "!",
            "h264parse",
            "!",
            "rtspclientsink",
            f"location={rtsp_url}/{pipeline_name}",
            "protocols=tcp"
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

    def _build_pipeline_front(self, source: str, options: PipelineOptions, input_type: str) -> List[str]:
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
            f"file-path={output_dir}/front_resnet18.txt",
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
            f"file-path={output_dir}/front_posture.txt",
            "!",
            "gvawatermark",
            "!",
            *self._get_rtsp_sink_elements(
                options.output_rtsp, "front_stream"
            ),
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
            f"file-path={output_dir}/front_mobilenetv2.txt",
            "file-format=json-lines",
            "!",
            "fakesink",
            "async=false",
            "sync=false",
        ]
        return pipeline

    def _build_pipeline_back(self, source: str, options: PipelineOptions, input_type: str) -> List[str]:
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
            f"file-path={output_dir}/back_posture.txt",
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
            f"file-path={output_dir}/back_resnet18.txt",
            "file-format=json-lines",
            "!",
            "gvafpscounter",
            "!",
            *self._get_rtsp_sink_elements(
                options.output_rtsp, "back_stream"
            ),
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
            "tee",
            "name=t",
            # Branch 1: ResNet18 classification (metadata only)
            "t.",
            "!",
            "queue",
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
            f"file-path={output_dir}/content_results.txt",
            "file-format=json-lines",
            "!",
            "fakesink",
            "async=false",
            "sync=false",
            # Branch 2: Direct RTSP output
            "t.",
            "!",
            *self._get_rtsp_sink_elements(
                options.output_rtsp, "content_stream"
            ),
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
                return False

        try:
            # Setup environment
            self._setup_environment()

            # Build pipeline based on name
            if pipeline_name == PipelineName.FRONT.value:
                pipeline_elements = self._build_pipeline_front(source, options, input_type)
            elif pipeline_name == PipelineName.BACK.value:
                pipeline_elements = self._build_pipeline_back(source, options, input_type)
            elif pipeline_name == PipelineName.CONTENT.value:
                pipeline_elements = self._build_pipeline_content(source, options, input_type)
            else:
                raise ValueError(f"Unknown pipeline: {pipeline_name}")

            # Build full command
            command = ["gst-launch-1.0.exe", "-e"] + pipeline_elements

            self.logger.info(f"Launching pipeline '{pipeline_name}'")
            self.logger.info(f"  Source: {source} (type: {input_type})")
            self.logger.info(f"  RTSP output: {options.output_rtsp}")
            self.logger.info(f"  Metadata dir: {options.output_dir}")
            self.logger.info(f"Command: {' '.join(command)}")

            # Create log file for pipeline output
            log_dir = Path("logs")
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

            self.logger.info(
                f"Pipeline '{pipeline_name}' started with PID: {process.pid}"
            )
            self.logger.info(f"  Log file: {log_file}")

            # Check for "Redistribute latency" in log file
            time.sleep(10)
            self.pipeline_log_handles[pipeline_name].flush()
            if self._check_redistribute_latency(log_file):
                self.logger.info("Pipeline initialized successfully")
            else:
                self.logger.warning("Pipeline may not have initialized properly")
            return True

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

    def monitor_pipeline(
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
            self.stop_all_pipelines(timeout=5.0)

            # Close any remaining log file handles
            for handle in self.pipeline_log_handles.values():
                try:
                    handle.close()
                except:
                    pass
            self.pipeline_log_handles.clear()

    def get_pose_stats(self, front_posture_file: str = "outputs/front_posture.txt") -> Dict:
        """
        Analyze front_posture.txt and generate pose statistics based on pose transitions
        
        Args:
            front_posture_file: Path to front_posture.txt file
            
        Returns:
            Dictionary with statistics:
            - student_count: Average person count
            - stand_count: Count of stand transitions (sit->stand->sit counts as one)
            - raise_up_count: Count of raise up transitions (not raising->raising->not raising counts as one)
            - stand_reid: List of student IDs with their stand transition counts
        """
        posture_file = Path(front_posture_file)
        
        if not posture_file.exists():
            self.logger.error(f"Front posture file not found: {posture_file}")
            return {
                "student_count": 0,
                "stand_count": 0,
                "raise_up_count": 0,
                "stand_reid": []
            }
        
        try:
            # Read all lines
            with open(posture_file, "r") as f:
                lines = f.readlines()
            
            if not lines:
                self.logger.warning("Front posture file is empty")
                return {
                    "student_count": 0,
                    "stand_count": 0,
                    "raise_up_count": 0,
                    "stand_reid": []
                }
            
            # Parse JSON objects
            frames = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        frames.append(obj)
                    except json.JSONDecodeError:
                        continue
            
            if not frames:
                self.logger.warning("No valid JSON frames found")
                return {
                    "student_count": 0,
                    "stand_count": 0,
                    "raise_up_count": 0,
                    "stand_reid": []
                }
            
            # Helper function to calculate IoU (Intersection over Union) between two bounding boxes
            def calculate_iou(bbox1, bbox2):
                """Calculate IoU between two bounding boxes"""
                x1_min = bbox1.get("x_min", 0)
                y1_min = bbox1.get("y_min", 0)
                x1_max = bbox1.get("x_max", 0)
                y1_max = bbox1.get("y_max", 0)
                
                x2_min = bbox2.get("x_min", 0)
                y2_min = bbox2.get("y_min", 0)
                x2_max = bbox2.get("x_max", 0)
                y2_max = bbox2.get("y_max", 0)
                
                # Calculate intersection
                x_left = max(x1_min, x2_min)
                y_top = max(y1_min, y2_min)
                x_right = min(x1_max, x2_max)
                y_bottom = min(y1_max, y2_max)
                
                if x_right < x_left or y_bottom < y_top:
                    return 0.0
                
                intersection = (x_right - x_left) * (y_bottom - y_top)
                
                # Calculate union
                area1 = (x1_max - x1_min) * (y1_max - y1_min)
                area2 = (x2_max - x2_min) * (y2_max - y2_min)
                union = area1 + area2 - intersection
                
                if union == 0:
                    return 0.0
                
                return intersection / union
            
            # Calculate statistics
            
            # 1. Student count at 60s, 120s, 180s (average)
            # Assuming 15 FPS: 60s = 900 frames, 120s = 1800 frames, 180s = 2700 frames
            target_frames = [900, 1800, 2700]
            person_counts = []
            
            for target_idx in target_frames:
                if target_idx < len(frames):
                    frame = frames[target_idx]
                    objects = frame.get("objects", [])
                    # Count objects with non-zero bounding box (valid detections)
                    count = sum(1 for obj in objects 
                              if obj.get("detection", {}).get("bounding_box", {}).get("x_max", 0) > 0)
                    person_counts.append(count)
            
            # Average student count
            student_count = int(sum(person_counts) / len(person_counts)) if person_counts else 0
            
            # 2. Track pose transitions with robustness
            # Minimum frames to confirm state change (at 15 FPS, 3 frames = 0.2 seconds)
            MIN_FRAMES_FOR_TRANSITION = 3
            IOU_THRESHOLD = 0.3  # IoU threshold for matching objects without ID
            
            # State tracking for students with IDs
            student_states = {}  # {student_id: {"is_standing": bool, "is_raising": bool, "stand_buffer": int, "raise_buffer": int}}
            student_stand_counts = {}
            student_raise_counts = {}
            
            # State tracking for objects without IDs (using ROI matching)
            unidentified_objects = []  # [{bbox, is_raising, raise_buffer, raise_count}]
            total_raise_count_no_id = 0
            
            for frame_idx, frame in enumerate(frames):
                objects = frame.get("objects", [])
                
                # Track which unidentified objects were matched this frame
                matched_unidentified = set()
                
                for obj in objects:
                    detection = obj.get("detection", {})
                    label = detection.get("label", "")
                    student_id = obj.get("id", 0)
                    bbox = detection.get("bounding_box", {})
                    
                    # Skip invalid detections (zero bounding box)
                    if bbox.get("x_max", 0) == 0:
                        continue
                    
                    # Determine current pose state
                    is_standing = label in ["stand", "stand_raise_up"]
                    is_raising = label in ["sit_raise_up", "stand_raise_up"]
                    
                    # Handle students with IDs
                    if student_id > 0:
                        # Initialize student state if not exists
                        if student_id not in student_states:
                            student_states[student_id] = {
                                "is_standing": False,
                                "is_raising": False,
                                "stand_buffer": 0,
                                "raise_buffer": 0
                            }
                            student_stand_counts[student_id] = 0
                            student_raise_counts[student_id] = 0
                        
                        state = student_states[student_id]
                        
                        # Standing state transition with buffer
                        if is_standing != state["is_standing"]:
                            state["stand_buffer"] += 1
                            if state["stand_buffer"] >= MIN_FRAMES_FOR_TRANSITION:
                                # Confirmed transition
                                if is_standing:  # Transition to standing
                                    student_stand_counts[student_id] += 1
                                state["is_standing"] = is_standing
                                state["stand_buffer"] = 0
                        else:
                            state["stand_buffer"] = 0
                        
                        # Raising state transition with buffer
                        if is_raising != state["is_raising"]:
                            state["raise_buffer"] += 1
                            if state["raise_buffer"] >= MIN_FRAMES_FOR_TRANSITION:
                                # Confirmed transition
                                if is_raising:  # Transition to raising
                                    student_raise_counts[student_id] += 1
                                state["is_raising"] = is_raising
                                state["raise_buffer"] = 0
                        else:
                            state["raise_buffer"] = 0
                    
                    # Handle students without IDs (only track raising)
                    else:
                        # Try to match with existing unidentified objects using IoU
                        best_match_idx = -1
                        best_iou = 0
                        
                        for idx, unid_obj in enumerate(unidentified_objects):
                            if idx in matched_unidentified:
                                continue
                            iou = calculate_iou(bbox, unid_obj["bbox"])
                            if iou > best_iou and iou >= IOU_THRESHOLD:
                                best_iou = iou
                                best_match_idx = idx
                        
                        if best_match_idx >= 0:
                            # Matched existing object
                            unid_obj = unidentified_objects[best_match_idx]
                            matched_unidentified.add(best_match_idx)
                            
                            # Update bbox
                            unid_obj["bbox"] = bbox
                            
                            # Raising state transition with buffer
                            if is_raising != unid_obj["is_raising"]:
                                unid_obj["raise_buffer"] += 1
                                if unid_obj["raise_buffer"] >= MIN_FRAMES_FOR_TRANSITION:
                                    # Confirmed transition
                                    if is_raising:  # Transition to raising
                                        unid_obj["raise_count"] += 1
                                        total_raise_count_no_id += 1
                                    unid_obj["is_raising"] = is_raising
                                    unid_obj["raise_buffer"] = 0
                            else:
                                unid_obj["raise_buffer"] = 0
                            
                            unid_obj["last_seen_frame"] = frame_idx
                        
                        else:
                            # New unidentified object
                            unidentified_objects.append({
                                "bbox": bbox,
                                "is_raising": is_raising,
                                "raise_buffer": 0,
                                "raise_count": 0,
                                "last_seen_frame": frame_idx
                            })
                
                # Remove stale unidentified objects (not seen for 30 frames = 2 seconds at 15 FPS)
                unidentified_objects = [
                    obj for obj in unidentified_objects
                    if frame_idx - obj["last_seen_frame"] < 30
                ]
            
            # 3. Calculate total counts
            stand_count = sum(student_stand_counts.values())
            raise_up_count = sum(student_raise_counts.values()) + total_raise_count_no_id
            
            # 4. Format student ID list (only students with stand transitions)
            stand_reid = [
                {"student_id": sid, "count": count}
                for sid, count in sorted(student_stand_counts.items())
                if count > 0
            ]
            
            stats = {
                "student_count": student_count,
                "stand_count": stand_count,
                "raise_up_count": raise_up_count,
                "stand_reid": stand_reid
            }
            
            self.logger.info(f"Pose statistics: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error analyzing pose statistics: {e}")
            return {
                "student_count": 0,
                "stand_count": 0,
                "raise_up_count": 0,
                "stand_reid": []
            }
