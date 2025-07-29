# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os
import json
import logging
import requests
from typing import Union
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from model.model import SummaryPayload
import traceback

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,  # Change to logging.INFO to reduce verbosity
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class SummarizationService:
    def __init__(self):
        logger.debug(f"SummarizationService initialized")

    def video_upload(self, video_path: Union[str, Path], base_url: str) -> dict:
        logger.debug(f"Starting video upload: {video_path}")

        try:
            video_path = Path(video_path)  # Ensure consistent use of Path

            if not video_path.exists():
                logger.error(f"File does not exist at path: {video_path}")
                raise HTTPException(
                    status_code=400, detail=f"Video file does not exist at path: {video_path}"
                )

            if not video_path.is_file():
                logger.error(f"Path is not a file: {video_path}")
                raise HTTPException(
                    status_code=400, detail=f"Path is not a file: {video_path}"
                )

            with open(video_path, "rb") as video_file:
                files = {"video": (video_path.name, video_file, "video/mp4")}
                upload_url = f"{base_url}/manager/videos/"
                logger.debug(f"Sending POST request to {upload_url}")

                response = requests.post(
                    upload_url, files=files, timeout=30
                )

            response.raise_for_status()
            logger.info(f"Video uploaded successfully: {video_path}")
            logger.debug(f"Upload response: {response.json()}")

            return response.json()

        except FileNotFoundError:
            logger.error(f"File not found: {video_path}")
            raise HTTPException(status_code=400, detail="Video file not found.")

        except IOError as e:
            logger.error(f"I/O error while reading file: {e}")
            raise HTTPException(status_code=500, detail="Error reading video file.")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload video: {type(e).__name__} - {e}")
            logger.debug(traceback.format_exc())
            status = e.response.status_code if e.response else 502
            detail = e.response.text if e.response else str(e)
            raise HTTPException(status_code=status, detail=f"Failed to upload video: {detail}")

    def create_summary(self, payload: SummaryPayload, base_url: str) -> dict:
        logger.debug(f"Creating summary for payload: {payload}")
        try:
            response = requests.post(f"{base_url}/manager/summary", json=payload.dict())
            response.raise_for_status()
            logger.info("Summary creation request successful.")
            logger.debug(f"Summary creation response: {response.json()}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create summary: {e}")
            raise HTTPException(
                status_code=502, detail=f"Failed to create summary: {str(e)}"
            )

    def get_summary_result(self, pipeline_id: str, base_url: str) -> dict:
        logger.debug(f"Fetching summary result for pipeline_id: {pipeline_id}")
        try:
            response = requests.get(f"{base_url}/manager/summary/{pipeline_id}")
            response.raise_for_status()

            json_data = response.json()
            logger.info(
                f"Summary result fetch successful for pipeline_id: {pipeline_id}"
            )
            # logger.debug(f"Summary result JSON: {json.dumps(json_data, indent=2)}")

            return json_data  # ✅ This returns the full parsed response
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to get summary result for pipeline_id {pipeline_id}: {e}"
            )
            raise HTTPException(
                status_code=502, detail=f"Failed to get summary result: {str(e)}"
            )
