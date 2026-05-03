#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
ROS2 Monitoring Stack Manager - Unified orchestration for monitoring and inference.

This script provides a cleaner way to run the ROS2 monitoring stack with:
- Concurrent monitoring of graph, resources, and timing
- Automatic data collection and organization
- Built-in analysis and visualization pipeline
- Session management and cleanup
"""

import argparse
import subprocess
import signal
import sys
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import threading


class MonitoringSession:
    """Manages a complete monitoring session with multiple concurrent monitors."""

    def __init__(self, session_name: Optional[str] = None, output_dir: Optional[str] = None,
                 target_node: Optional[str] = None, interval: float = 5.0,
                 monitor_resources: bool = True, monitor_graph: bool = True,
                 auto_visualize: bool = True, pid_only: bool = False,
                 remote_ip: Optional[str] = None, remote_user: str = 'ubuntu',
                 ros_domain_id: Optional[int] = None,
                 enable_gpu: bool = False, enable_npu: bool = False,
                 algorithm: Optional[str] = None,
                 use_sim_time: bool = False):
        """
        Initialize a monitoring session.

        Args:
            session_name: Name for this monitoring session
            output_dir: Directory to store all outputs
            target_node: Specific ROS2 node to monitor
            interval: Update interval in seconds
            monitor_resources: Enable resource monitoring
            monitor_graph: Enable graph monitoring
            auto_visualize: Automatically generate visualizations on exit
            pid_only: Monitor PIDs only (no thread details)
            remote_ip: IP address of the remote system running the ROS2 pipeline
            remote_user: SSH username for the remote system (default: ubuntu)
            algorithm: Algorithm/experiment label — sessions are grouped under
                       monitoring_sessions/<algorithm>/<timestamp>/
        """
        self.algorithm = algorithm
        self.session_name = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_dir:
            self.output_dir = Path(output_dir)
        elif algorithm:
            safe = algorithm.replace(' ', '_').replace('/', '_')
            self.output_dir = Path(f"./monitoring_sessions/{safe}/{self.session_name}")
        else:
            self.output_dir = Path(f"./monitoring_sessions/{self.session_name}")
        self.target_node = target_node
        self.interval = interval
        self.monitor_resources = monitor_resources
        self.monitor_graph = monitor_graph
        self.auto_visualize = auto_visualize
        self.pid_only = pid_only
        self.remote_ip = remote_ip
        self.remote_user = remote_user
        self.ros_domain_id = ros_domain_id  # explicit override; None = auto-detect
        self.enable_gpu = enable_gpu or bool(remote_ip)  # auto-enable GPU when remote
        self.enable_npu = enable_npu  # explicit only — not auto-enabled
        self.use_sim_time = use_sim_time

        # Process tracking
        self.processes: List[subprocess.Popen] = []
        self.running = False

        # Output files
        self.graph_log = self.output_dir / "graph_timing.csv"
        self.topology_log = self.output_dir / "graph_topology.json"
        self.resource_log = self.output_dir / "resource_usage.log"
        self.gpu_log = self.output_dir / "gpu_usage.log"
        self.npu_log = self.output_dir / "npu_usage.log"
        self.visualization_dir = self.output_dir / "visualizations"

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n\n🛑 Received shutdown signal. Cleaning up...")
        self.stop()

    def setup(self):
        """Setup the monitoring session directories and files."""
        print(f"📁 Setting up monitoring session: {self.session_name}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.visualization_dir.mkdir(parents=True, exist_ok=True)

        # Create session info file
        info_file = self.output_dir / "session_info.txt"
        with open(info_file, 'w') as f:
            f.write(f"Session: {self.session_name}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if self.algorithm:
                f.write(f"Algorithm: {self.algorithm}\n")
            f.write(f"Target Node: {self.target_node or 'All nodes'}\n")
            f.write(f"Interval: {self.interval}s\n")
            f.write(f"Monitor Resources: {self.monitor_resources}\n")
            f.write(f"Monitor Graph: {self.monitor_graph}\n")
            f.write(f"Output Directory: {self.output_dir}\n")
            if self.remote_ip:
                f.write(f"Remote System: {self.remote_user}@{self.remote_ip}\n")
            f.write("-" * 80 + "\n")

        if self.algorithm:
            print(f"   Algorithm: {self.algorithm}")
        if self.remote_ip:
            print(f"   Remote system: {self.remote_user}@{self.remote_ip}")
        print(f"   Output directory: {self.output_dir}")

    def _get_remote_domain_id(self) -> Optional[int]:
        """SSH to the remote machine and return its ROS_DOMAIN_ID, or None on failure."""
        try:
            result = subprocess.run(
                ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                 '-o', 'StrictHostKeyChecking=no',
                 f'{self.remote_user}@{self.remote_ip}',
                 # Login shell so .bashrc / launch-sourced exports are visible
                 r'bash -l -c "echo ${ROS_DOMAIN_ID:-not_set}"'],
                capture_output=True, text=True, timeout=10,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                return None  # SSH failed — don't override local env
            val = result.stdout.strip()
            return int(val) if val.isdigit() else None
        except Exception:
            return None

    def _build_remote_env(self) -> dict:
        """Build subprocess environment with DDS peer discovery for a remote host."""
        env = os.environ.copy()
        if self.remote_ip:
            if self.ros_domain_id is not None:
                # User explicitly specified --ros-domain-id; use it and skip auto-detect.
                env['ROS_DOMAIN_ID'] = str(self.ros_domain_id)
                print(f"   ✅ ROS_DOMAIN_ID={self.ros_domain_id} (explicit override).")
            else:
                # Auto-detect the remote's ROS_DOMAIN_ID and align locally.
                # This is the most common reason DDS peer discovery silently fails.
                remote_domain = self._get_remote_domain_id()
                local_domain  = env.get('ROS_DOMAIN_ID', '0')
                if remote_domain is not None and str(remote_domain) != str(local_domain):
                    print("   ⚠  ROS_DOMAIN_ID mismatch detected:")
                    print(f"      local={local_domain}  remote={remote_domain}")
                    print(f"      Setting ROS_DOMAIN_ID={remote_domain} for monitoring processes.")
                    env['ROS_DOMAIN_ID'] = str(remote_domain)
                elif remote_domain is not None:
                    print(f"   ✅ ROS_DOMAIN_ID={remote_domain} matches on both machines.")
                else:
                    print("   ℹ  Could not detect remote ROS_DOMAIN_ID (SSH auth issue?).")
                    print(f"      Using local ROS_DOMAIN_ID={local_domain}.")
                    print("      Tip: use --ros-domain-id <id> to set it explicitly.")

            env['ROS_LOCALHOST_ONLY'] = '0'
            # CycloneDDS: explicit unicast peer + disable multicast (works across subnets)
            env['CYCLONEDDS_URI'] = (
                '<CycloneDDS><Domain>'
                '<General><AllowMulticast>false</AllowMulticast></General>'
                '<Discovery><Peers>'
                f'<Peer address="{self.remote_ip}"/>'
                '</Peers></Discovery>'
                '</Domain></CycloneDDS>'
            )
            # FastDDS / rmw_fastrtps – unicast peer list (always override)
            env['ROS_STATIC_PEERS'] = self.remote_ip
        return env

    def start_monitors(self):
        """Start all monitoring processes."""
        self.running = True
        script_dir = Path(__file__).parent

        # Prepare subprocess environment (adds DDS peer vars when monitoring remotely)
        proc_env = self._build_remote_env()

        print("\n🚀 Starting monitoring processes...")
        if self.remote_ip:
            print(f"   🌐 Monitoring remote system: {self.remote_user}@{self.remote_ip}")
            print("      Ensure ROS_DOMAIN_ID matches on both machines.")

        # Start graph monitor if enabled
        if self.monitor_graph:
            cmd = [
                sys.executable,
                str(script_dir / "ros2_graph_monitor.py"),
                "--interval", str(self.interval),
                "--log", str(self.graph_log),
                "--topology", str(self.topology_log),
                "--show-processing"
            ]

            if self.target_node:
                cmd.extend(["--node", self.target_node])

            if self.remote_ip:
                cmd.extend(["--remote-ip", self.remote_ip,
                             "--remote-user", self.remote_user])

            if self.use_sim_time:
                cmd.append("--use-sim-time")

            # Skip the interactive countdown when launched programmatically
            cmd.append("--no-countdown")

            print("   📊 Starting graph monitor...")
            print(f"      Logging to: {self.graph_log}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=proc_env,
            )
            self.processes.append(process)

            # Start thread to display output
            threading.Thread(
                target=self._stream_output,
                args=(process, "GRAPH"),
                daemon=True
            ).start()

        # Start resource monitor if enabled
        if self.monitor_resources:
            cmd = [
                sys.executable,
                str(script_dir / "monitor_resources.py"),
                "--interval", str(self.interval),
                "--memory",
                "--log", str(self.resource_log)
            ]

            # Add --threads flag only if not pid_only mode
            if not self.pid_only:
                cmd.append("--threads")

            if self.enable_gpu:
                cmd.extend(["--gpu", "--gpu-log", str(self.gpu_log)])
            if self.enable_npu:
                cmd.extend(["--npu", "--npu-log", str(self.npu_log)])

            if self.remote_ip:
                cmd.extend(["--remote-ip", self.remote_ip,
                             "--remote-user", self.remote_user])

            print("   💻 Starting resource monitor...")
            print(f"      Logging to: {self.resource_log}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=proc_env,
            )
            self.processes.append(process)

            # Start thread to display output
            threading.Thread(
                target=self._stream_output,
                args=(process, "RESOURCE"),
                daemon=True
            ).start()

        print("\n✅ All monitors started. Collecting data...")
        print("   Press Ctrl+C to stop monitoring and generate visualizations.\n")

    def _stream_output(self, process: subprocess.Popen, label: str):
        """Stream process output with label."""
        for line in process.stdout:
            if line.strip():
                print(f"[{label}] {line.rstrip()}")

    def wait(self):
        """Wait for monitoring processes to complete."""
        try:
            while self.running:
                # Check if any process has died unexpectedly
                for process in self.processes:
                    if process.poll() is not None:
                        print(f"\n⚠️  Monitor process exited unexpectedly (exit code: {process.returncode})")
                        # Show any error output
                        stderr = process.stderr.read()
                        if stderr:
                            print(f"Error output: {stderr}")

                time.sleep(1)
        except KeyboardInterrupt:
            pass

    def stop(self):
        """Stop all monitoring processes."""
        if not self.running:
            return

        self.running = False
        print("\n🛑 Stopping monitors...")

        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

        # Update session info
        info_file = self.output_dir / "session_info.txt"
        with open(info_file, 'a') as f:
            f.write(f"\nStopped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print("✅ All monitors stopped.")

    def visualize(self):
        """Generate visualizations from collected data."""
        if not self.auto_visualize:
            print("\n⏭️  Skipping visualization (disabled)")
            return

        print("\n📈 Generating visualizations...")
        script_dir = Path(__file__).parent

        # Visualize timing data if graph monitor was running
        if self.monitor_graph and self.graph_log.exists():
            print("   📊 Creating timing visualizations...")
            cmd = [
                sys.executable,
                str(script_dir / "visualize_timing.py"),
                str(self.graph_log),
                "--output-dir", str(self.visualization_dir),
                "--delays",
                "--frequencies"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"      ✅ Timing plots saved to {self.visualization_dir}")
            else:
                print(f"      ⚠️  Error generating timing plots: {result.stderr}")

            # Pipeline graph – rqt_graph-style directed view with KPI metrics
            print("   🗺️  Creating pipeline graph (rqt_graph style)...")
            graph_cmd = [
                sys.executable,
                str(script_dir / "visualize_graph.py"),
                str(self.graph_log),
                "--output-dir", str(self.visualization_dir),
                "--no-show",
            ]
            if self.topology_log.exists():
                graph_cmd.extend(["--topology", str(self.topology_log)])
            result = subprocess.run(graph_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"      ✅ Pipeline graph saved to {self.visualization_dir}/pipeline_graph.png")
            else:
                print(f"      ⚠️  Error generating pipeline graph: {result.stderr}")

        # Visualize resource data if resource monitor was running
        if self.monitor_resources and self.resource_log.exists():
            print("   💻 Creating resource visualizations...")
            cmd = [
                sys.executable,
                str(script_dir / "visualize_resources.py"),
                str(self.resource_log),
                "--output-dir", str(self.visualization_dir),
                "--cores",
                "--heatmap",
                "--top", "10"
            ]
            if self.gpu_log.exists():
                cmd.extend(["--gpu-log", str(self.gpu_log)])
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"      ✅ Resource plots saved to {self.visualization_dir}")
            else:
                print(f"      ⚠️  Error generating resource plots: {result.stderr}")

        # Visualize GPU data if collected
        if self.gpu_log.exists():
            print("   🖥️  Creating GPU visualizations...")
            gpu_cmd = [
                sys.executable,
                str(script_dir / "visualize_gpu.py"),
                str(self.gpu_log),
                "--output-dir", str(self.visualization_dir),
                "--save",
            ]
            result = subprocess.run(gpu_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"      ✅ GPU plots saved to {self.visualization_dir}")
            else:
                print(f"      ⚠️  Error generating GPU plots: {result.stderr}")

        # Visualize NPU data if collected
        if self.npu_log.exists():
            print("   🧠 Creating NPU visualizations...")
            npu_cmd = [
                sys.executable,
                str(script_dir / "visualize_npu.py"),
                str(self.npu_log),
                "--output-dir", str(self.visualization_dir),
                "--no-show",
            ]
            result = subprocess.run(npu_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"      ✅ NPU plots saved to {self.visualization_dir}")
            else:
                print(f"      ⚠️  Error generating NPU plots: {result.stderr}")

        print(f"\n📊 Session complete! Results saved to: {self.output_dir}")
        print(f"   Visualizations: {self.visualization_dir}")

        print("\n\U0001f4a1 To compare across multiple runs:")
        algo_flag = f" --algorithm {self.algorithm}" if self.algorithm else ""
        print(f"   uv run python src/view_average.py{algo_flag}          # avg KPIs across last 5 sessions")
        print(f"   uv run python src/view_average.py{algo_flag} --plot   # same + save bar-chart PNGs")

    def run(self):
        """Run the complete monitoring session."""
        self.setup()
        self.start_monitors()
        self.wait()
        self.stop()
        self.visualize()


def main():
    parser = argparse.ArgumentParser(
        description="ROS2 Monitoring Stack Manager - Unified monitoring orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor all nodes with default settings
  %(prog)s

  # Monitor a specific node with custom session name
  %(prog)s --node /slam_toolbox --session slam_performance_test

  # Quick 60-second monitoring session
  %(prog)s --node /controller_server --duration 60

  # Monitor only graph (no resource monitoring)
  %(prog)s --graph-only --interval 2

  # Monitor only resources (no graph monitoring)
  %(prog)s --resources-only

  # Custom output directory
  %(prog)s --output-dir ./my_analysis --session experiment_1

  # Disable auto-visualization
  %(prog)s --no-visualize

The monitoring session will run until you press Ctrl+C.
All data is automatically saved and visualized (unless --no-visualize is used).
        """
    )

    parser.add_argument(
        '--session', '-s',
        type=str,
        help='Session name (default: timestamp)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='Output directory for all session data (default: ./monitoring_sessions/<session_name>)'
    )

    parser.add_argument(
        '--node', '-n',
        type=str,
        help='Specific ROS2 node to monitor (e.g., /slam_toolbox)'
    )

    parser.add_argument(
        '--interval', '-i',
        type=float,
        default=5.0,
        help='Update interval in seconds (default: 5.0)'
    )

    parser.add_argument(
        '--duration', '-d',
        type=int,
        help='Duration in seconds (default: run until Ctrl+C). '
             'When monitoring a remote system, allow at least 90s — '
             'CycloneDDS peer discovery typically takes 30-60s before '
             'topic messages start flowing (e.g. --duration 180).'
    )

    parser.add_argument(
        '--graph-only',
        action='store_true',
        help='Monitor only graph/timing (no resource monitoring)'
    )

    parser.add_argument(
        '--resources-only',
        action='store_true',
        help='Monitor only resources (no graph monitoring)'
    )

    parser.add_argument(
        '--no-visualize',
        action='store_true',
        help='Skip automatic visualization generation'
    )

    parser.add_argument(
        '--pid-only',
        action='store_true',
        help='Monitor PIDs only (no thread details for resource monitoring)'
    )

    parser.add_argument(
        '--gpu',
        action='store_true',
        help='Enable Intel GPU monitoring (auto-enabled when --remote-ip is used). '
             'Requires intel_gpu_top with CAP_PERFMON: '
             'sudo setcap cap_perfmon+eip $(which intel_gpu_top)'
    )

    parser.add_argument(
        '--npu',
        action='store_true',
        help='Enable Intel NPU monitoring via sysfs (/sys/class/accel/accel0/). '
             'No special capabilities required. Works locally and remotely.'
    )

    parser.add_argument(
        '--remote-ip',
        type=str,
        default=None,
        help='IP address of the remote system running the ROS2 pipeline. '
             'Enables cross-machine monitoring via SSH (resources) and DDS '
             'peer discovery (graph). Requires matching ROS_DOMAIN_ID.'
    )

    parser.add_argument(
        '--remote-user',
        type=str,
        default='ubuntu',
        help='SSH username for the remote system (default: ubuntu)'
    )

    parser.add_argument(
        '--ros-domain-id',
        type=int,
        default=None,
        metavar='ID',
        help='Explicitly set ROS_DOMAIN_ID for both DDS discovery and SSH remote detection. '
             'Skips auto-detection. Use this when the remote sets ROS_DOMAIN_ID at runtime '
             '(e.g. in a launch script) rather than in ~/.bashrc. '
             'Example: --ros-domain-id 46'
    )

    parser.add_argument(
        '--algorithm', '-a',
        type=str,
        default=None,
        help='Algorithm or experiment label.  Sessions are grouped under '
             'monitoring_sessions/<algorithm>/<timestamp>/ so you can easily '
             'compare runs of the same algorithm over time.  '
             'E.g. --algorithm slam_toolbox  or  --algorithm "nav2 default"'
    )

    parser.add_argument(
        '--use-sim-time',
        action='store_true',
        default=False,
        help='Pass --use-sim-time to the graph monitor. Auto-detected when '
             '/clock is published (Gazebo/sim); only needed if auto-detection '
             'fires too late or is not desired.'
    )

    parser.add_argument(
        '--list-sessions',
        action='store_true',
        help='List all previous monitoring sessions and exit'
    )

    args = parser.parse_args()

    # Handle list sessions
    if args.list_sessions:
        sessions_dir = Path("./monitoring_sessions")
        if not sessions_dir.exists():
            print("No monitoring sessions found.")
            return

        # Collect all session dirs: both flat (<ts>/) and grouped (<algo>/<ts>/)
        def _iter_sessions(root: Path):
            for child in sorted(root.iterdir(), reverse=True):
                if not child.is_dir():
                    continue
                info = child / "session_info.txt"
                if info.exists():
                    yield child, info
                else:
                    # Might be an algorithm subdirectory — recurse one level
                    for grandchild in sorted(child.iterdir(), reverse=True):
                        if grandchild.is_dir():
                            ginfo = grandchild / "session_info.txt"
                            if ginfo.exists():
                                yield grandchild, ginfo

        entries = list(_iter_sessions(sessions_dir))
        if not entries:
            print("No monitoring sessions found.")
            return

        print("\n📂 Previous Monitoring Sessions:\n")
        last_algo = None
        for session_path, info_file in entries:
            # Determine algorithm group label
            parent = session_path.parent
            algo_label = None if parent == sessions_dir else parent.name
            if algo_label != last_algo:
                header = f"── {algo_label} ──" if algo_label else "── (no algorithm) ──"
                print(f"  {header}")
                last_algo = algo_label
            print(f"   {session_path.name}:")
            with open(info_file, 'r') as f:
                lines = [line.strip() for line in f.readlines()[:5]]
                for line in lines:
                    if line and not line.startswith('-'):
                        print(f"      {line}")
            print()
        return

    # Validate conflicting options
    if args.graph_only and args.resources_only:
        print("Error: Cannot specify both --graph-only and --resources-only")
        sys.exit(1)

    # Determine what to monitor
    monitor_resources = not args.graph_only
    monitor_graph = not args.resources_only

    # Create and run session
    session = MonitoringSession(
        session_name=args.session,
        output_dir=args.output_dir,
        target_node=args.node,
        interval=args.interval,
        monitor_resources=monitor_resources,
        monitor_graph=monitor_graph,
        auto_visualize=not args.no_visualize,
        pid_only=args.pid_only,
        remote_ip=args.remote_ip,
        remote_user=args.remote_user,
        ros_domain_id=args.ros_domain_id,
        enable_gpu=args.gpu,
        enable_npu=args.npu,
        algorithm=args.algorithm,
        use_sim_time=args.use_sim_time,
    )

    # Handle duration if specified
    if args.duration:
        def stop_after_duration():
            time.sleep(args.duration)
            print(f"\n⏰ Duration limit reached ({args.duration}s)")
            session.stop()

        timer_thread = threading.Thread(target=stop_after_duration, daemon=True)
        timer_thread.start()

    try:
        session.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        session.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()
