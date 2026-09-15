# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import re
import time
import requests
from utils.common import logger, settings

try:  # Keep backward compatibility if VSS_SEARCH_URL still defined elsewhere
    from config import VSS_SEARCH_URL  # type: ignore
except Exception:
    # Fallback: derive from VIDEO_UPLOAD_ENDPOINT if present
    VSS_SEARCH_URL = settings.VIDEO_UPLOAD_ENDPOINT or ""

uploaded_files = set()
TERMINAL_BATCH_STATES = {
    "completed",
    "completed_with_errors",
    "failed",
    "cancelled",
}


def sanitize_file_path(file_path):
    file_name = os.path.basename(file_path)
    sanitized_name = re.sub(r"[^a-zA-Z0-9_\-./]", "_", file_name)
    return sanitized_name


def upload_single_video_with_retry(file_path, max_retries=3):
    """Upload one video through Pipeline Manager and return its video ID."""
    sanitized_name = sanitize_file_path(file_path)
    file_size = None
    try:
        file_size = os.path.getsize(file_path)
    except Exception:
        pass
    logger.info(
        f"[Upload] Starting upload attempts for {file_path} (sanitized='{sanitized_name}' size={file_size})"
    )

    camera_name = None
    try:
        parts = file_path.split(os.sep)
        for i, part in enumerate(parts):
            if re.match(r"^\d{4}-\d{2}-\d{2}$", part) and i + 2 < len(parts):
                camera_name = parts[i + 2]  # date/hour/camera layout
                break
        if not camera_name:
            # fallback: use parent directory name
            camera_name = os.path.basename(os.path.dirname(file_path))
    except Exception:
        camera_name = "unknown"
    tags = f"{camera_name}"
    for attempt in range(1, max_retries + 1):
        try:
            with open(file_path, "rb") as file:
                logger.debug(f"Upload target base: {VSS_SEARCH_URL}")
                files = {
                    "video": (sanitized_name, file, "video/mp4"),
                }
                data = {"tags": tags}

                upload_response = requests.post(
                    f"{VSS_SEARCH_URL}/manager/videos/",
                    files=files,
                    data=data,
                )
                upload_response.raise_for_status()

                # Extract video ID from response
                video_data = upload_response.json()
                video_id = video_data.get("videoId")
                if not video_id:
                    raise ValueError("No video ID returned from upload")

                logger.info(f"[Upload] Uploaded {file_path} -> videoId={video_id}")
                return video_id
        except Exception as e:
            if attempt == max_retries:
                if isinstance(e, requests.exceptions.HTTPError):
                    status_code = (
                        e.response.status_code
                        if getattr(e, "response", None) is not None
                        else "unknown"
                    )
                    logger.error(
                        f"HTTP error {status_code} occurred while processing {file_path} after {max_retries} retries: {str(e)}"
                    )
                else:
                    logger.error(
                        f"Error occurred while processing {file_path} after {max_retries} retries: {str(e)}"
                    )
                return None

            backoff_time = 2**attempt
            error_type = (
                "HTTP error"
                if isinstance(e, requests.exceptions.HTTPError)
                else "Error"
            )
            logger.warning(
                f"[Upload] {error_type} attempt {attempt}/{max_retries} for {file_path}: "
                f"{str(e)} | retrying in {backoff_time}s"
            )
            time.sleep(backoff_time)

    return None


def submit_embedding_batch(video_ids, max_retries=3):
    """Submit one Pipeline Manager batch that delegates to DataPrep."""
    endpoint = f"{VSS_SEARCH_URL}/manager/videos/search-embeddings-batch"
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(endpoint, json={"videoIds": video_ids})
            response.raise_for_status()
            job_id = response.json().get("job_id")
            if not job_id:
                raise ValueError("No job_id returned from batch submission")
            logger.info(
                f"[Upload] Submitted {len(video_ids)} videos for batch embedding, "
                f"job ID: {job_id}"
            )
            return job_id
        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    f"[Upload] Failed to submit embedding batch after "
                    f"{max_retries} attempts: {str(e)}"
                )
                return None
            backoff_time = 2**attempt
            logger.warning(
                f"[Upload] Embedding batch submission failed on attempt "
                f"{attempt}/{max_retries}: {str(e)}. Retrying in "
                f"{backoff_time} seconds..."
            )
            time.sleep(backoff_time)
    return None


def wait_for_embedding_batch(job_id):
    """Poll Pipeline Manager until a DataPrep batch job reaches a terminal state."""
    endpoint = f"{VSS_SEARCH_URL}/manager/videos/search-embeddings-jobs/{job_id}"
    deadline = time.monotonic() + settings.BATCH_JOB_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            status = response.json()
            state = status.get("state")
            if state in TERMINAL_BATCH_STATES:
                logger.info(
                    f"[Upload] Embedding batch {job_id} finished with state {state}"
                )
                return status
        except Exception as e:
            logger.warning(
                f"[Upload] Failed to poll embedding batch {job_id}: {str(e)}"
            )

        time.sleep(settings.BATCH_JOB_POLL_INTERVAL_SECONDS)

    logger.error(
        f"[Upload] Timed out after {settings.BATCH_JOB_TIMEOUT_SECONDS:.1f} "
        f"seconds waiting for embedding batch {job_id}"
    )
    return None


def upload_videos_to_dataprep(file_paths):
    """Upload files through Pipeline Manager and embed them in DataPrep batches."""
    requested_paths = list(file_paths)
    start_batch = time.time()
    logger.info(f"[Upload] Starting batch upload of {len(requested_paths)} files")
    previously_uploaded_paths = {
        path for path in requested_paths if path in uploaded_files
    }
    successful_paths = set(previously_uploaded_paths)
    video_paths_by_id = {}

    for file_path in requested_paths:
        if file_path in uploaded_files:
            logger.debug(f"[Upload] Skipping already uploaded file {file_path}")
            continue
        video_id = upload_single_video_with_retry(file_path)
        if video_id:
            video_paths_by_id[video_id] = file_path

    video_ids = list(video_paths_by_id)
    batch_size = max(1, settings.WATCH_BATCH_SIZE)
    for start in range(0, len(video_ids), batch_size):
        batch_ids = video_ids[start : start + batch_size]
        job_id = submit_embedding_batch(batch_ids)
        status = wait_for_embedding_batch(job_id) if job_id else None
        if not status:
            continue

        for item in status.get("items", []):
            if item.get("status") != "success":
                logger.error(
                    f"[Upload] Batch embedding failed for "
                    f"{item.get('identifier', 'unknown item')}: "
                    f"{item.get('message', 'unknown error')}"
                )
                continue
            video_id = item.get("video_id") or item.get("identifier")
            file_path = video_paths_by_id.get(video_id)
            if file_path:
                successful_paths.add(file_path)

    for file_path in successful_paths:
        uploaded_files.add(file_path)
        if (
            file_path not in previously_uploaded_paths
            and settings.DELETE_PROCESSED_FILES
            and os.path.exists(file_path)
        ):
            try:
                os.remove(file_path)
                logger.info(f"[Upload] Deleted processed file {file_path}")
            except OSError as del_err:
                logger.warning(f"[Upload] Failed to delete {file_path}: {del_err}")

    failed_count = len(requested_paths) - len(successful_paths)
    batch_elapsed = time.time() - start_batch
    logger.info(
        f"[Upload] Batch complete: success={failed_count == 0} "
        f"processed={len(successful_paths) - len(previously_uploaded_paths)} "
        f"skipped={len(previously_uploaded_paths)} total={len(requested_paths)} "
        f"elapsed={batch_elapsed:.2f}s"
    )
    return failed_count == 0
