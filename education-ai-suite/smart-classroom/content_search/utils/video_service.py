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
        prompt: str = "Please summarize this video.",
        chunk_duration: int = None
    ):
        url = f"{self.base_url}/preprocess"
        
        payload = {
            "minio_video_key": file_key,
            "reuse_existing": True,
            "tags": tags if (tags and len(tags) > 0) else ["video"]
        }

        if prompt is not None:
            payload["prompt"] = prompt
        
        if chunk_duration is not None:
            payload["chunk_duration_s"] = chunk_duration

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