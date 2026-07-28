"""CLI entry point for videostream-analytics.

Subcommands:
  serve   — start HTTP API server (default if no subcommand given)
  stream  — single-source mode, output events to stdout (dev/debug)
  health  — check running serve instance health
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time

import httpx


def _setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def cmd_serve(args):
    """Start HTTP API server."""
    import uvicorn
    from shared.config import load_config
    from service import create_app

    config = load_config(args.config)
    log_level = config.logging.get("level", "INFO").upper()
    _setup_logging(log_level)

    host = args.host or config.server.host
    port = args.port or config.server.port

    app = create_app(config)
    uvicorn.run(app, host=host, port=port, log_level=log_level.lower())


def cmd_stream(args):
    """Single-source streaming mode — output events to stdout."""
    import os
    from shared.config import load_config, SourceConfig, expand_path
    from stream_monitor.rtsp_monitor import StreamPipeline
    from sinks import StdoutSink, NullSink, WebhookSink

    config = load_config(args.config)
    log_level = config.logging.get("level", "INFO").upper()
    _setup_logging(log_level)

    logger = logging.getLogger(__name__)

    if args.sink == "stdout":
        sink = StdoutSink()
    elif args.sink == "null":
        sink = NullSink()
    elif args.sink == "webhook":
        sink = WebhookSink(config.webhook)
    else:
        sink = StdoutSink()

    source = SourceConfig(
        source_id=args.source_id,
        source_url=args.rtsp_url,
    )

    data_dir = os.path.join(expand_path(config.data_dir), args.source_id)
    os.makedirs(data_dir, exist_ok=True)

    pipeline = StreamPipeline(
        source=source,
        defaults=config.defaults,
        data_dir=data_dir,
        sink=sink,
    )

    stop_event = False

    def _signal_handler(sig, frame):
        nonlocal stop_event
        stop_event = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Starting stream: %s → %s (sink=%s)", args.source_id, args.rtsp_url, args.sink)
    pipeline.start()

    try:
        while not stop_event:
            time.sleep(0.5)
    finally:
        pipeline.stop()
        sink.close()
        logger.info("Stream stopped")


def cmd_health(args):
    """Check health of a running serve instance."""
    url = f"http://{args.host}:{args.port}/health"
    try:
        resp = httpx.get(url, timeout=5)
        data = resp.json()
        if resp.status_code == 200 and data.get("status") == "ok":
            print(json.dumps(data, indent=2))
            sys.exit(0)
        else:
            print(f"Unhealthy: {resp.status_code} {data}", file=sys.stderr)
            sys.exit(1)
    except httpx.ConnectError:
        print(f"Cannot connect to {url}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="videostream-analytics",
        description="Smart Building video stream analytics",
    )
    # Defaults are set on the main parser only; subparsers use SUPPRESS so
    # omitting a flag after the subcommand doesn't overwrite a value the user
    # passed before the subcommand.
    parser.set_defaults(config=None, host=None, port=None)
    parser.add_argument("--config", "-c", default=argparse.SUPPRESS,
                        help="Path to config.yaml")
    parser.add_argument("--host", default=argparse.SUPPRESS,
                        help="Listen host (serve mode)")
    parser.add_argument("--port", type=int, default=argparse.SUPPRESS,
                        help="Listen port (serve mode)")
    subparsers = parser.add_subparsers(dest="command")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start HTTP API server")
    p_serve.add_argument("--config", "-c", default=argparse.SUPPRESS, help="Path to config.yaml")
    p_serve.add_argument("--host", default=argparse.SUPPRESS, help="Listen host")
    p_serve.add_argument("--port", type=int, default=argparse.SUPPRESS, help="Listen port")

    # stream
    p_stream = subparsers.add_parser("stream", help="Single-source mode (dev/debug)")
    p_stream.add_argument("--config", "-c", default=argparse.SUPPRESS, help="Path to config.yaml")
    p_stream.add_argument("--source-id", required=True, help="Source identifier")
    p_stream.add_argument("--rtsp-url", required=True, help="RTSP stream URL")
    p_stream.add_argument("--use-case", default="default", help="Use case label")
    p_stream.add_argument("--sink", choices=["stdout", "webhook", "null"], default="stdout",
                          help="Event output sink (default: stdout)")

    # health
    p_health = subparsers.add_parser("health", help="Check running instance health")
    p_health.add_argument("--host", default="127.0.0.1", help="Target host")
    p_health.add_argument("--port", type=int, default=8999, help="Target port")

    args = parser.parse_args()

    if args.command is None:
        cmd_serve(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "stream":
        cmd_stream(args)
    elif args.command == "health":
        cmd_health(args)


if __name__ == "__main__":
    main()
