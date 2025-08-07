# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import requests
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict
from fastapi.responses import FileResponse
from config import FRIGATE_BASE_URL


class FrigateService:
    def __init__(self, base_url: str = FRIGATE_BASE_URL):
        self.base_url = base_url

    def get_camera_names(self) -> Dict[str, list]:
        """Get mapping of camera names to detected objects from Frigate"""
        try:
            response = requests.get(f"{self.base_url}/api/config")
            response.raise_for_status()
            config = response.json()
            cameras = config.get("cameras", {})
            
            camera_object_map = {
                cam_name: cam_cfg.get("objects", {}).get("track", [])
                for cam_name, cam_cfg in cameras.items()
            }
            print(camera_object_map)
            return camera_object_map

        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=502, detail=f"Failed to connect to Frigate: {str(e)}"
            )

    @staticmethod
    def _validate_time_range(start_time: int, end_time: int):
        """Validate time range parameters"""
        if end_time <= start_time:
            raise HTTPException(
                status_code=400, detail="End time must be after start time"
            )
        if (end_time - start_time) > 300:  # 5 minute limit
            raise HTTPException(
                status_code=400, detail="Clip duration cannot exceed 300 seconds"
            )

    async def get_camera_events(self, camera_name: str) -> dict:
        """Get list of events for a specific camera"""
        url = f"{self.base_url}/api/events?camera={camera_name}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Frigate events API error: {e.response.text}",
            )
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=502, detail=f"Failed to contact Frigate: {str(e)}"
            )

    MEDIA_BASE_PATH = "/media/exports"

    def get_clip_from_timestamps(
        self, camera_name: str, start_time: int, end_time: int, download: bool = False
    ) -> StreamingResponse:
        """
        Call Frigate's /start/:start_ts/end/:end_ts/clip.mp4 API to retrieve a video clip.

        Args:
            camera_name (str): Name of the camera.
            start_time (int): Start timestamp (e.g. 1749531197).
            end_time (int): End timestamp (e.g. 1749531212).
            download (bool): If True, download the file.

        Returns:
            StreamingResponse: Video stream response.
        """
        if end_time <= start_time:
            raise HTTPException(
                status_code=400, detail="End time must be after start time"
            )

        url = f"{self.base_url}/api/{camera_name}/start/{start_time}/end/{end_time}/clip.mp4"
        if download:
            url += "?download=1"

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            return StreamingResponse(
                response.iter_content(chunk_size=8192),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": response.headers.get(
                        "Content-Disposition", "inline"
                    )
                },
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="Clip not found for specified time range"
                )
            raise HTTPException(
                status_code=502, detail=f"Frigate error: {e.response.text}"
            )
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=502, detail=f"Failed to connect to Frigate: {str(e)}"
            )