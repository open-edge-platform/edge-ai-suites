# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import requests
import os
import tempfile
import subprocess
import aiofiles
import logging
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from api.endpoints.frigate_api import FrigateService
from model.model import Sampling, Evam, SummaryPayload
from api.endpoints.summarization_api import SummarizationService
from config import VSS_SUMMARY_URL
from config import VSS_SEARCH_URL

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG if you want more verbose logs
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

frigate_service = FrigateService()
summarization_service = SummarizationService()


class VmsService:
    def __init__(self, frigate_service, summarization_service):
        self.frigate_service = frigate_service
        self.summarization_service = summarization_service
        self.vss_summary_url: str = VSS_SUMMARY_URL
        self.vss_search_url: str = VSS_SEARCH_URL
        logger.info("VmsService initialized.")

    async def upload_video_to_summarizer(
        self, camera_name: str, start_time: float, end_time: float, is_search: bool
    ) -> dict:
        """Fetches clip from Frigate, writes to temp file, uploads it, and returns videoId."""
        try:
            stream_response = self.frigate_service.get_clip_from_timestamps(
                camera_name, start_time, end_time, download=True
            )
            logger.info("Clip retrieved from Frigate.")
        except Exception as e:
            logger.error(f"Failed to get clip: {e}")
            return {
                "status": 500,
                "message": "Failed to retrieve video clip from camera",
            }

        # Write stream to temp file while checking size
        temp_file_size = 0
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        logger.info(f"Temporary file created at: {tmp_path}")

        try:
            async with aiofiles.open(tmp_path, "wb") as f:
                async for chunk in stream_response.body_iterator:
                    await f.write(chunk)
                    temp_file_size += len(chunk)

            # Check if video is too small (likely empty)
            if temp_file_size <= 100:
                logger.warning(
                    f"No video found for given timestamps (file size: {temp_file_size} bytes)"
                )
                os.remove(tmp_path)
                return {
                    "status": 404,
                    "message": "No video footage available for the selected time range. Please try different timestamps.",
                }

            logger.info(
                f"Stream written to temporary file. Size: {temp_file_size} bytes"
            )
        except Exception as e:
            logger.error(f"Failed to process video stream: {e}")
            return {"status": 500, "message": "Failed to process video stream"}

        # Upload file
        try:
            if is_search:
                upload_result = self.summarization_service.video_upload(
                    tmp_path, self.vss_search_url
                )
            else:
                upload_result = self.summarization_service.video_upload(
                    tmp_path, self.vss_summary_url
                )

            if not upload_result or "videoId" not in upload_result:
                return {
                    "status": 500,
                    "message": "Video upload failed - no videoId returned",
                }

            logger.info(f"Video uploaded, videoId: {upload_result.get('videoId')}")
            return {"status": 200, "message": upload_result["videoId"]}
        except Exception as e:
            logger.error(f"Video upload failed: {e}")
            return {"status": 500, "message": "Video upload failed"}
        finally:
            try:
                if os.path.exists(tmp_path):
                    logger.info(f"Cleaning up temporary file: {tmp_path}")
                    os.remove(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file: {e}")

    async def summarize(
        self, camera_name: str, start_time: float, end_time: float
    ) -> dict:
        logger.info(
            f"Starting summarization for camera: {camera_name}, "
            f"start_time: {start_time}, end_time: {end_time}"
        )

        upload_resp = await self.upload_video_to_summarizer(
            camera_name, start_time, end_time, False
        )
        if upload_resp["status"] != 200:
            return upload_resp

        try:
            payload = SummaryPayload(
                videoId=upload_resp["message"],
                title=f"summary_{camera_name}_{int(start_time)}",
                sampling=Sampling(chunkDuration=8, samplingFrame=8),
                evam=Evam(evamPipeline="object_detection"),
            )
            pipeline = self.summarization_service.create_summary(
                payload, self.vss_summary_url
            )

            if not pipeline or "summaryPipelineId" not in pipeline:
                return {
                    "status": 500,
                    "message": "Summary creation failed - no pipelineId returned",
                }

            logger.info(
                f"Summary pipeline created with ID: {pipeline.get('summaryPipelineId')}"
            )
            return {"status": 200, "message": pipeline["summaryPipelineId"]}
        except Exception as e:
            logger.error(f"Failed to create summary: {e}")
            return {"status": 500, "message": "Failed to create video summary"}

    def summary(self, summary_id: str):
        logger.info(f"Fetching summary result for ID: {summary_id}")
        try:
            result = summarization_service.get_summary_result(
                summary_id, self.vss_summary_url
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve summary from summarization service for summary id {summary_id}: {e}"
            )
            raise

        video_summary = result.get("summary")

        # If summary is empty or None, return fallback structure
        if not video_summary:
            logger.info("Final summary not ready yet.")
            # Extract summarized frames with fallback structure
            frame_summaries = result.get("frameSummaries", [])
            simplified_frame_summaries = []

            for frame in frame_summaries:
                simplified_frame_summaries.append(
                    {
                        "startFrame": frame.get("startFrame"),
                        "endFrame": frame.get("endFrame"),
                        "status": frame.get("status"),
                        "summary": frame.get("summary"),
                    }
                )

            return {
                "summary": "Final summary is being generated please wait for a while.",
                "frameSummaries": simplified_frame_summaries,
            }

        logger.info("Summary retrieved successfully.")
        return {"summary": video_summary}

    async def search_embeddings(
        self, camera_name: str, start_time: float, end_time: float
    ) -> dict:
        """
        Uploads video from the specified camera and time range,
        then triggers the search-embeddings API.

        Returns:
            str: Message from the search-embeddings API response.
        """
        logger.info(
            f"Starting search_embeddings for camera={camera_name}, start={start_time}, end={end_time}"
        )

        try:
            upload_resp = await self.upload_video_to_summarizer(
                camera_name, start_time, end_time, True
            )
            if upload_resp["status"] != 200:
                return upload_resp
        except Exception as e:
            logger.error(f"Failed to upload video for embedding search: {e}")
            raise

        url = f"{self.vss_search_url}/manager/videos/search-embeddings/{upload_resp['message']}"
        logger.info(f"Calling search-embeddings API: {url}")

        try:
            response = requests.post(url)
            response.raise_for_status()
            message = response.json().get("message", "No message in response.")
            logger.info(f"Embedding search response: {message}")
            return {
                "status": 200,
                "video_id": upload_resp["message"],
                "message": message,
            }
        except requests.RequestException as e:
            logger.error(f"Search embeddings API failed: {e}")
            raise
