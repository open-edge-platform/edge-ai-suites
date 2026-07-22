#!/usr/bin/env python3
"""Mock videostream-analytics service.

Simulates the videostream-analytics microservice by periodically sending
motion events to the MCP Server's EventsEndpoint. Also generates dummy
video segment files for the video-summary service to consume.

Usage:
    python mock_videostream.py [options]

Options:
    --events-url    EventsEndpoint URL (default: http://localhost:3101/events)
    --segments-dir  Directory to write dummy segment files (default: ./segments)
    --monitor-id    Monitor ID to simulate (default: cam-01)
    --interval      Seconds between events (default: 10)
    --count         Number of events to send, 0=infinite (default: 5)
    --use-case      Use case type: child_safety|elder_wakeup|fridge_monitor (default: child_safety)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


# Scenario templates — different event patterns per use case
SCENARIOS = {
    "child_safety": [
        "Child playing near table edge",
        "Child running in hallway",
        "Child climbing on furniture",
        "Child jumping from chair",
        "Child playing with sharp object",
    ],
    "elder_wakeup": [
        "Person lying in bed, no movement",
        "Person sitting up slowly",
        "Person standing from bed",
        "Person walking to bathroom",
        "Person returned to bed",
    ],
    "fridge_monitor": [
        "Fridge door opened, items visible",
        "Person taking milk from fridge",
        "Fridge contents: low on eggs",
        "Person putting items back",
        "Fridge door closed",
    ],
}


def create_dummy_segment(segments_dir: Path, monitor_id: str, index: int) -> str:
    """Create a dummy mp4 file to simulate a video segment."""
    monitor_dir = segments_dir / monitor_id
    monitor_dir.mkdir(parents=True, exist_ok=True)

    filename = f"clip-{index:04d}.mp4"
    filepath = monitor_dir / filename

    # Write minimal dummy content (not a real mp4, but sufficient for mock testing)
    filepath.write_bytes(b"\x00" * 1024)

    # Return relative path (what videostream-analytics would report)
    return f"{monitor_id}/{filename}"


def send_event(events_url: str, monitor_id: str, video_path: str, scenario_desc: str) -> bool:
    """Send a motion event to the EventsEndpoint."""
    event = {
        "sourceId": monitor_id,
        "type": "motion",
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "video_path": video_path,
            "description": scenario_desc,
        },
    }

    data = json.dumps(event).encode()
    req = urllib.request.Request(
        events_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True
            print(f"  ⚠ Unexpected status: {resp.status}")
            return False
    except urllib.error.URLError as e:
        print(f"  ✗ Failed to send event: {e}")
        return False


def check_health(events_url: str) -> bool:
    """Check if EventsEndpoint is reachable."""
    health_url = events_url.rsplit("/", 1)[0] + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Mock videostream-analytics service")
    parser.add_argument("--events-url", default="http://localhost:3101/events",
                        help="EventsEndpoint URL")
    parser.add_argument("--segments-dir", default="./segments",
                        help="Directory to write dummy segment files")
    parser.add_argument("--monitor-id", default="cam-01",
                        help="Monitor ID to simulate")
    parser.add_argument("--interval", type=float, default=10,
                        help="Seconds between events")
    parser.add_argument("--count", type=int, default=5,
                        help="Number of events to send (0=infinite)")
    parser.add_argument("--use-case", default="child_safety",
                        choices=list(SCENARIOS.keys()),
                        help="Use case scenario type")
    args = parser.parse_args()

    segments_dir = Path(args.segments_dir).resolve()
    segments_dir.mkdir(parents=True, exist_ok=True)
    scenarios = SCENARIOS[args.use_case]

    print(f"╔════════════════════════════════════════════╗")
    print(f"║  Mock Videostream-Analytics                ║")
    print(f"╚════════════════════════════════════════════╝")
    print(f"  Events URL:   {args.events_url}")
    print(f"  Segments dir: {segments_dir}")
    print(f"  Monitor ID:   {args.monitor_id}")
    print(f"  Use case:     {args.use_case}")
    print(f"  Interval:     {args.interval}s")
    print(f"  Count:        {'infinite' if args.count == 0 else args.count}")
    print()

    # Check connectivity
    print("  Checking EventsEndpoint health...", end=" ")
    if check_health(args.events_url):
        print("✓ reachable")
    else:
        print("✗ not reachable")
        print(f"  Make sure MCP Server is running with events endpoint on the expected port.")
        print(f"  Start with: node packages/mcp-server/dist/index.js --config config.yaml.example")
        sys.exit(1)

    print()
    sent = 0
    index = 0

    try:
        while True:
            if args.count > 0 and sent >= args.count:
                break

            scenario_desc = scenarios[index % len(scenarios)]
            video_path = create_dummy_segment(segments_dir, args.monitor_id, index)

            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"  [{timestamp}] Sending event #{index}: \"{scenario_desc}\"")
            print(f"           segment: {video_path}")

            success = send_event(args.events_url, args.monitor_id, video_path, scenario_desc)
            if success:
                sent += 1
                print(f"           → sent ✓ ({sent}/{args.count if args.count > 0 else '∞'})")
            else:
                print(f"           → failed ✗")

            index += 1
            print()

            if args.count == 0 or sent < args.count:
                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n  Stopped by user.")

    print(f"\n  Done. Sent {sent} events, created {index} segment files in {segments_dir}")


if __name__ == "__main__":
    main()
