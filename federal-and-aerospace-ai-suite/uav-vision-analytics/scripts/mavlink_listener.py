# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Listen to all incoming MAVLink messages and print their type, fields, and values.
Useful for discovering available telemetry data before adding new overlay fields
to the gvapython telemetry overlay script.

Usage:
  python3 mavlink_listener.py [--port PORT] [--filter MSG_TYPE] [--output FILE]

Examples:
  python3 mavlink_listener.py
  python3 mavlink_listener.py --filter GLOBAL_POSITION_INT
  python3 mavlink_listener.py --filter VFR_HUD --output hud_log.txt
  python3 mavlink_listener.py --port 14550

Inside the container:
  docker exec -it dlstreamer-pipeline-server \
    python3 /home/pipeline-server/scripts/mavlink_listener.py
"""

import argparse
import sys
from pymavlink import mavutil


def listen(port: int, msg_filter: str | None, output_path: str | None) -> None:
    conn_str = f"udpin:0.0.0.0:{port}"
    print(f"Connecting to {conn_str} ...")

    master = mavutil.mavlink_connection(conn_str)

    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(
        f"Connected — System {master.target_system}, "
        f"Component {master.target_component}"
    )
    print(f"Listening (filter={msg_filter or 'ALL'}). Press Ctrl+C to stop.\n")

    out = open(output_path, "w") if output_path else None  # noqa: SIM115
    seen_types: set[str] = set()

    try:
        while True:
            msg = master.recv_match(blocking=True)
            if msg is None:
                continue

            msg_type = msg.get_type()

            if msg_filter and msg_type != msg_filter:
                continue

            fields = {
                k: v
                for k, v in msg.to_dict().items()
                if k != "mavpackettype"
            }

            # Print a separator the first time a new message type appears
            if msg_type not in seen_types:
                seen_types.add(msg_type)
                separator = f"\n{'─' * 60}\nNew message type: {msg_type}\n{'─' * 60}"
                print(separator)
                if out:
                    out.write(separator + "\n")

            line = f"[{msg_type}] {fields}"
            print(line)
            if out:
                out.write(line + "\n")
                out.flush()

    except KeyboardInterrupt:
        print(f"\nStopped. Seen {len(seen_types)} message type(s): {sorted(seen_types)}")
    finally:
        if out:
            out.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAVLink message listener — discover available telemetry fields"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=14541,
        help="UDP port to listen on (default: 14541)",
    )
    parser.add_argument(
        "--filter",
        dest="msg_filter",
        default=None,
        metavar="MSG_TYPE",
        help="Only print messages of this type (e.g. GLOBAL_POSITION_INT, VFR_HUD)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Optional file path to save messages to",
    )
    args = parser.parse_args()
    listen(args.port, args.msg_filter, args.output)


if __name__ == "__main__":
    main()
