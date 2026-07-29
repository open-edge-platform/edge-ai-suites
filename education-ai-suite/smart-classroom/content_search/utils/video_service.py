#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import httpx
import json
import traceback

class VideoService:
    def __init__(self):
        host = os.getenv("PREPROCESS_HOST", "127.0.0.1")
        port = os.getenv("PREPROCESS_PORT", "8001")
        self.base_url = f"http://{host}:{port}"
        self.timeout = 900.0

    async def trigger_summarization(
        self,
        file_key: str,
        bucket_name: str,
        tags: list = None,
        prompt: str = (
            "Please summarize this classroom video segment. "
            "Focus on the teaching activities, lecture topics, "
            "key knowledge points being explained, "
            "any content written or displayed on the blackboard/screen, "
            "student behaviors (e.g. raising hands, taking notes, discussing, distracted, leaving the classroom), "
            "and notable student-teacher interactions."
        ),
        chunk_duration: int = None,
        run_id: str = None
    ):
        url = f"{self.base_url}/preprocess"

        payload = {
            "file_key": file_key,
            "reuse_existing": True,
            "tags": tags
        }

        if prompt is not None:
            payload["prompt"] = prompt

        if chunk_duration is not None:
            payload["chunk_duration_s"] = chunk_duration

        if run_id is not None:
            payload["run_id"] = run_id

        print(f"[VideoService] Calling -> {url}")
        print(f"[VideoService] Payload: {json.dumps(payload, ensure_ascii=False)}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        content = await response.aread()
                        return {"error": f"HTTP {response.status_code}", "detail": content.decode()}

                    last_data = {}
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk_data = json.loads(line)
                                if chunk_data.get("type") == "chunk":
                                    print(f"  > Processing {chunk_data.get('chunk_id')}...")
                                last_data = chunk_data
                            except:
                                continue
                    return last_data

        except Exception as e:
            traceback.print_exc()
            return {"error": "Connection failed", "message": str(e)}

video_service = VideoService()