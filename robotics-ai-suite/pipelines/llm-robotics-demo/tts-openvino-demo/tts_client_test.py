# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# -*- encoding: utf-8 -*-
"""Simple client to test tts_server.py submit_tts interface.

Usage:
    python3 tts_client_test.py --text "Pick up the apple and place it in the box."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

import websockets


async def send_submit_tts(uri: str, text: str, language: str = "EN") -> dict:
    request = {
        "action": "submit_tts",
        "request_id": str(uuid.uuid4()),
        "text": text,
        "language": language,
    }

    async with websockets.connect(uri, subprotocols=["json"], ping_interval=None) as ws:
        await ws.send(json.dumps(request, ensure_ascii=False))
        response = await ws.recv()
        return json.loads(response)


async def send_health(uri: str) -> dict:
    request = {
        "action": "health",
        "request_id": str(uuid.uuid4()),
    }

    async with websockets.connect(uri, subprotocols=["json"], ping_interval=None) as ws:
        await ws.send(json.dumps(request, ensure_ascii=False))
        response = await ws.recv()
        return json.loads(response)


def main():
    parser = argparse.ArgumentParser(description="Simple submit_tts client tester")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="tts server host")
    parser.add_argument("--port", type=int, default=10096, help="tts server port")
    parser.add_argument("--text", type=str, default="This is a submit tts interface test.", help="text to submit")
    parser.add_argument("--language", type=str, default="EN", help="language field in request")
    parser.add_argument("--skip-health", action="store_true", help="skip health request before submit")
    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}"
    print(f"[TTS CLIENT TEST] server: {uri}")

    if not args.skip_health:
        health = asyncio.run(send_health(uri))
        print("[TTS CLIENT TEST] health:")
        print(json.dumps(health, ensure_ascii=False, indent=2))
        if not health.get("accepted", False):
            print("[TTS CLIENT TEST] health check failed, stop testing submit_tts.")
            return

    result = asyncio.run(send_submit_tts(uri, args.text, args.language))
    print("[TTS CLIENT TEST] submit_tts response:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
