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


def sanitize_file_path(file_path):
    file_name = os.path.basename(file_path)
    sanitized_name = re.sub(r"[^a-zA-Z0-9_\-./]", "_", file_name)
    return sanitized_name



def upload_single_video_with_retry(file_path, max_retries=3):
    """Upload a single video with retry mechanism"""
    retry_count = 1
    sanitized_name = sanitize_file_path(file_path)
    file_size = None
    try:
        file_size = os.path.getsize(file_path)
    except Exception:
        pass
    logger.info(f"[Upload] Starting upload attempts for {file_path} (sanitized='{sanitized_name}' size={file_size})")

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
    while retry_count < max_retries:
        try:
            with open(file_path, "rb") as file:
                logger.debug(f"Upload target base: {VSS_SEARCH_URL}")
                # Step 1: Upload video to get ID

                files = {
                    "video": (sanitized_name, file, "video/mp4"),
                }
                data = {
                    "tags": tags
                }

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

                # Step 2: Process video for search embeddings
                embedding_response = requests.post(
                    f"{VSS_SEARCH_URL}/manager/videos/search-embeddings/{video_id}",
                )
                embedding_response.raise_for_status()

                logger.info(f"[Upload] Search embeddings processed for videoId={video_id} ({file_path})")
                return True  # Successfully processed
        except (requests.exceptions.HTTPError, Exception) as e:
            retry_count += 1

            # Determine if we should retry or exit
            if retry_count > max_retries:
                # Log error with additional context for HTTP errors
                if isinstance(e, requests.exceptions.HTTPError):
                    status_code = (
                        e.response.status_code if hasattr(e, "response") else "unknown"
                    )
                    logger.error(
                        f"HTTP error {status_code} occurred while processing {file_path} after {max_retries} retries: {str(e)}"
                    )
                else:
                    logger.error(
                        f"Error occurred while processing {file_path} after {max_retries} retries: {str(e)}"
                    )
                return False

            # Calculate backoff time and retry
            backoff_time = 2**retry_count  # Exponential backoff 2,4,8,...
            error_type = (
                "HTTP error"
                if isinstance(e, requests.exceptions.HTTPError)
                else "Error"
            )
            logger.warning(f"[Upload] {error_type} attempt {retry_count-1}/{max_retries} for {file_path}: {str(e)} | retrying in {backoff_time}s")
            time.sleep(backoff_time)

    # This should never be reached due to the return statements above, but adding as a safety measure
    return False


def upload_videos_to_dataprep(file_paths):
    start_batch = time.time()
    logger.info(f"[Upload] Starting batch upload of {len(file_paths)} files")
    all_success = True
    processed = 0
    skipped = 0
    for file_path in file_paths:
        if file_path in uploaded_files:
            skipped += 1
            logger.debug(f"[Upload] Skipping already uploaded file {file_path}")
            continue
        single_start = time.time()
        success = upload_single_video_with_retry(file_path)
        elapsed_single = time.time() - single_start
        if success:
            processed += 1
            uploaded_files.add(file_path)
            logger.info(f"[Upload] Completed upload for {file_path} in {elapsed_single:.2f}s (progress {processed}/{len(file_paths)})")
            if settings.DELETE_PROCESSED_FILES:
                try:
                    os.remove(file_path)
                    logger.info(f"[Upload] Deleted processed file {file_path}")
                except Exception as del_err:
                    logger.warning(f"[Upload] Failed to delete {file_path}: {del_err}")
        else:
            all_success = False
            logger.error(f"[Upload] Failed upload for {file_path} after retries (elapsed {elapsed_single:.2f}s)")
    batch_elapsed = time.time() - start_batch
    logger.info(f"[Upload] Batch complete: success={all_success} processed={processed} skipped={skipped} total={len(file_paths)} elapsed={batch_elapsed:.2f}s")
    return all_success