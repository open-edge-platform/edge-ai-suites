# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


from pathlib import Path
from functools import cache
import sys
import os
import argparse
import logging
import datetime
import re
import string
import unicodedata
import streamlit as st
from PIL import Image
import time
import random
from io import BytesIO
import base64
import requests
import shutil
import tempfile
import copy
from openai import OpenAI
from urllib.parse import quote

from utils import image_to_url, video_to_url

PROMPT_LENGTH_LIMIT = 1024
ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"

# Get environment variables
BACKEND_VQA_BASE_URL = os.getenv("BACKEND_VQA_BASE_URL", "http://localhost:8399")
BACKEND_SEARCH_BASE_URL = os.getenv("BACKEND_SEARCH_BASE_URL", "http://localhost:6008")
BACKEND_DATAPREP_BASE_URL = os.getenv("BACKEND_DATAPREP_BASE_URL", "http://localhost:9990")
# Base URL the *browser* uses to stream media from dataprep. It defaults to the
# service URL the app itself calls, which is already host-published in the
# compose deployments. Override it when the app-facing URL is not reachable from
# the browser (e.g. an in-cluster Kubernetes service name).
DATAPREP_PUBLIC_BASE_URL = os.getenv("DATAPREP_PUBLIC_BASE_URL") or BACKEND_DATAPREP_BASE_URL

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "openai/clip-vit-base-patch32")
VLM_MODEL_NAME=os.getenv("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")

DATA_INGEST_WITH_DETECT = os.getenv("DATA_INGEST_WITH_DETECT", "False").lower() == "true"
DATA_INGEST_FRAME_INTERVAL = int(os.getenv("DATA_INGEST_FRAME_INTERVAL", 15))
DATAPREP_BUCKET_NAME = os.getenv("DATAPREP_BUCKET_NAME", "vsqa")
DATAPREP_MEDIA_ROUTE_PREFIX = "/v1/dataprep/media/download"
VIDEO_FILE_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpeg", ".mpg", ".ts", ".wmv")
# Cap on the media pulled into memory for the VLM's inline data URL.
DATAPREP_MEDIA_MAX_BYTES = int(os.getenv("DATAPREP_MEDIA_MAX_BYTES", 512 * 1024 * 1024))
DATAPREP_JOB_POLL_INTERVAL = float(os.getenv("DATAPREP_JOB_POLL_INTERVAL", 5))
DATAPREP_JOB_TIMEOUT = float(os.getenv("DATAPREP_JOB_TIMEOUT", 36000))
# A poll may fail transiently (read timeout, restarted pod, momentary 5xx) while
# the job itself keeps running. Give up only after this many consecutive
# failures, otherwise the UI reports an error for an ingest that is still in
# flight and a subsequent ingest collides with it.
DATAPREP_JOB_POLL_RETRIES = int(os.getenv("DATAPREP_JOB_POLL_RETRIES", 5))
DATAPREP_MEDIA_FETCH_TIMEOUT = float(os.getenv("DATAPREP_MEDIA_FETCH_TIMEOUT", 300))

# User-defined metadata fields (from meta/<basename>.json sidecars) the UI filters
# on. `timestamp` is reserved by the dataprep metadata contract (frame time in
# seconds), hence the distinct `capture_date` name for the capture date.
METADATA_CAMERA_FIELD = os.getenv("METADATA_CAMERA_FIELD", "camera")
METADATA_DATE_FIELD = os.getenv("METADATA_DATE_FIELD", "capture_date")

HOST_IP_IDDRESS = os.getenv("host_ip", "localhost")
VISUAL_SEARCH_QA_UI_PORT = os.getenv("VISUAL_SEARCH_QA_UI_PORT", "17580")

MOUNT_DATA_PATH = "/home/user/data"
HOST_DATA_PATH = os.getenv("HOST_DATA_PATH", "/home/user/data")

MAX_MAX_NUM_SEARCH_RESULTS = int(os.getenv('MAX_MAX_NUM_SEARCH_RESULTS', 200))
DEFAULT_NUM_SEARCH_RESULTS = int(os.getenv('DEFAULT_NUM_SEARCH_RESULTS', 10))
SHOW_RESULT_PER_ROW = int(os.getenv('SHOW_RESULT_PER_ROW', 5))

DEFAULT_MAX_PIXELS_TO_VLM = "360*420"
    
logger = logging.getLogger('visual_search_qa')
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s.%(msecs)03d [%(name)s]: %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
)

def encode_base64_content_from_url(content_url: str) -> str:
    """Encode a content retrieved from a remote url to base64 format."""
    with requests.get(content_url) as response:
        response.raise_for_status()
        result = base64.b64encode(response.content).decode('utf-8')

    return result

def video_url_to_base64(video_url):
    """
    Convert a video from a URL to a Base64-encoded string.

    Args:
        video_url (str): The URL of the video.

    Returns:
        str: The Base64-encoded video content with the MIME type.
    """
    try:
        # Download the video from the URL
        response = requests.get(video_url, stream=True)
        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)

        # Read the video content
        video_content = response.content

        # Encode the video content in Base64
        base64_video = base64.b64encode(video_content).decode('utf-8')

        # Format the Base64 string with the MIME type
        base64_video_with_mime = f"data:video/mp4;base64,{base64_video}"

        return base64_video_with_mime

    except Exception as e:
        print(f"Error converting video to Base64: {e}")
        return None

def compose_media_url(id, type):
    return f"http://{HOST_IP_IDDRESS}:{VISUAL_SEARCH_QA_UI_PORT}/media/{id}{type}"

def compose_dataprep_media_url(meta: dict, base_url: str = None) -> str:
    """Build the dataprep streaming URL for a search hit.

    ``GET /media/download`` advertises ``Accept-Ranges: bytes`` and answers Range
    requests with ``206 Partial Content``, so handing the URL to the browser lets
    the media element seek without the whole file ever being read by this app.
    The retriever already returns a ready-made relative URL; the ids are used as
    a fallback so the UI keeps working with producers that omit it.
    """
    base = (base_url or DATAPREP_PUBLIC_BASE_URL).rstrip("/")

    # Only accept a relative path under the known download route: the value comes
    # from the vector DB, and the result is both handed to the browser and
    # fetched server-side, so an absolute or escaping URL must never pass through.
    rel_url = meta.get("video_rel_url") or ""
    if rel_url.startswith(DATAPREP_MEDIA_ROUTE_PREFIX) and "//" not in rel_url and ".." not in rel_url:
        return f"{base}{rel_url}"

    video_id = meta.get("video_id")
    if not video_id:
        return ""

    url = f"{base}/v1/dataprep/media/download?video_id={quote(str(video_id), safe='')}"
    bucket_name = meta.get("bucket_name") or DATAPREP_BUCKET_NAME
    if bucket_name:
        url += f"&bucket_name={quote(str(bucket_name), safe='')}"
    return url


def is_video_meta(meta: dict) -> bool:
    """Whether a search hit refers to a video, from the normalized metadata."""
    if "video" in (meta.get("type") or ""):
        return True
    if (meta.get("content_type") or "") == "video":
        return True
    name = meta.get("file_path") or meta.get("filename") or ""
    return name.lower().endswith(VIDEO_FILE_EXTENSIONS)


def fetch_media_bytes(meta: dict):
    """Read a search hit's media, preferring the dataprep download endpoint.

    Only used where the bytes themselves are needed (the VLM expects an inline
    data URL). Rendering goes straight to the URL so the browser can range-fetch.
    """
    # Rebuilt against the backend URL: the media_url on the hit targets the
    # browser, and that address is not necessarily routable from this container.
    media_url = compose_dataprep_media_url(meta, base_url=BACKEND_DATAPREP_BASE_URL)
    if media_url:
        try:
            with requests.get(media_url, timeout=DATAPREP_MEDIA_FETCH_TIMEOUT, stream=True) as response:
                response.raise_for_status()
                declared = int(response.headers.get("Content-Length") or 0)
                if declared > DATAPREP_MEDIA_MAX_BYTES:
                    logger.error(
                        "Media at %s is %d bytes, over the %d byte limit; skipping",
                        media_url, declared, DATAPREP_MEDIA_MAX_BYTES,
                    )
                    return None
                # Servers may omit Content-Length, so cap while reading too.
                chunks, total = [], 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    total += len(chunk)
                    if total > DATAPREP_MEDIA_MAX_BYTES:
                        logger.error(
                            "Media at %s exceeds the %d byte limit; skipping",
                            media_url, DATAPREP_MEDIA_MAX_BYTES,
                        )
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch media from {media_url}: {e}; falling back to file")

    file_path = meta.get("file_path", "")
    if file_path and os.path.exists(file_path):
        if os.path.getsize(file_path) > DATAPREP_MEDIA_MAX_BYTES:
            logger.error("Media file %s is over the %d byte limit; skipping", file_path, DATAPREP_MEDIA_MAX_BYTES)
            return None
        with open(file_path, "rb") as media_file:
            return media_file.read()

    return None


def helper_map2host(file_path: str):
    """
    Helper function to map a file path from the container to the host.
    """
    if file_path.startswith(MOUNT_DATA_PATH):
        return file_path.replace(MOUNT_DATA_PATH, HOST_DATA_PATH)
    else:
        return file_path
    
def helper_map2container(file_path: str):
    """
    Helper function to map a file path from the host to the container.
    """
    if file_path.startswith(HOST_DATA_PATH):
        return file_path.replace(HOST_DATA_PATH, MOUNT_DATA_PATH)
    else:
        return file_path

def normalize_meta(meta: dict) -> dict:
    """Map the dataprep canonical metadata onto the field names the UI uses.

    The dataprep microservice writes a backend-neutral contract
    (``source_path``, ``content_type``, ``timestamp``); the UI works with
    ``file_path``, ``type`` and ``video_pin_second``. Both layouts are accepted
    so the UI keeps working against either producer.
    """
    normalized = dict(meta)

    # dataprep spells frame_type inconsistently by media kind: video frames are
    # written as "FULL_FRAME" while images are written as "full_frame" (likewise
    # for crops). Canonicalise to lower case so anything reading this field sees
    # one spelling regardless of which producer path wrote the row.
    frame_type = normalized.get("frame_type")
    if isinstance(frame_type, str):
        normalized["frame_type"] = frame_type.lower()

    if not normalized.get("file_path"):
        normalized["file_path"] = normalized.get("source_path", "")

    if not normalized.get("type"):
        content_type = normalized.get("content_type", "")
        normalized["type"] = "local_video" if content_type == "video" else "local_image"

    if normalized.get("video_pin_second") is None:
        normalized["video_pin_second"] = normalized.get("timestamp", 0)

    if not normalized.get("media_url"):
        normalized["media_url"] = compose_dataprep_media_url(normalized)

    return normalized


def helper_map2ingest(file_path: str):
    """Map a host path to a path relative to the dataprep ingest root.

    The dataprep microservice resolves ``dir_path`` against its own ingest root,
    which is the same host directory (``HOST_DATA_PATH``) bind-mounted into that
    container, so only the part below the shared root is meaningful to it. Both
    the host and the container spelling of the shared root are accepted.
    """
    path = file_path.strip()
    for root in (HOST_DATA_PATH, MOUNT_DATA_PATH):
        if root and path.startswith(root):
            path = path[len(root):]
            break
    return path.strip("/") or "."


def filter_output(results, de_duplicate=False):
    logger.info("Filtering output")
    # results is a list of dictionaries, each containing "id" and "distance" and "meta"
    # each "meta" contains "file_path", "type", "timestamp", "video_pin_second"(for video) and other fields
    filtered_results = []
    keep = [True] * len(results)
    for i in range(len(results)):
        if not keep[i]:
            continue
        if "video" not in results[i]["meta"]["type"]:
            # image file, deduplicate by file name
            target_file_path = results[i]["meta"].get("file_path")
            for j in range(i+1, len(results)):
                if not keep[j]:
                    continue
                cur_file_path = results[j]["meta"].get("file_path")
                if target_file_path == cur_file_path:
                    keep[j] = False
        else:
            # video file, deduplicate by video file name and timestamp
            target_file_path = results[i]["meta"].get("file_path")
            target_pin = results[i]["meta"].get("video_pin_second")
            for j in range(i+1, len(results)):
                cur_file_path = results[j]["meta"].get("file_path")
                cur_pin = results[j]["meta"].get("video_pin_second")
                if de_duplicate:
                    if target_file_path == cur_file_path and abs(float(target_pin)-float(cur_pin)) < st.session_state.threshold:
                        keep[j] = False
                else:
                    if target_file_path == cur_file_path and abs(float(target_pin)-float(cur_pin)) < 1e-8:
                        keep[j] = False

    for i in range(len(results)):
        if keep[i]:
            filtered_results.append(results[i])
    return filtered_results


def send_query_request(text: str = "", image_base64: str = "", k: int = 10, where: dict | None = None):
    url = f"{BACKEND_SEARCH_BASE_URL}/query"

    query_block: dict = {"query_id": "vsqa-search", "top_k": k}

    if text:
        logger.info(f"Querying {text}")
        query_block["query"] = text
    elif image_base64:
        logger.info("Querying image")
        query_block["image"] = {"type": "image_base64", "image_base64": image_base64}
    else:
        logger.error("No query or image provided")
        return None

    if where is not None:
        query_block["where"] = where

    results = {}

    try:
        response = requests.post(url, json=[query_block], timeout=100)
        response.raise_for_status()

        body = response.json()
        errors = body.get("errors", [])
        if errors:
            logger.error(f"Retriever query errors: {errors}")
            return []

        query_results = body.get("results", [])
        if not query_results:
            return []

        items = query_results[0].get("items", [])
        results = [
            {
                "id": item.get("metadata", {}).get("id", str(idx)),
                "distance": item.get("score", 0.0),
                "meta": normalize_meta(item.get("metadata", {})),
            }
            for idx, item in enumerate(items)
        ]

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")
        return []

    return results
    

def get_vqa_msg(prompt):
    system_msg = {
        "role": ROLE_SYSTEM,
        "content": []
    }
    user_msg = {
        "role": ROLE_USER,
        "content": []
    }
    assistant_msg = {
        "role": ROLE_ASSISTANT,
        "content": []
    }
    history_msg = []
    if len(st.session_state.messages) == 0:
        system_msg["content"].append({
                "type": "text",
                "text": "You are a helpful assistant. Please remember the order of the images passed in, this is important for answering"
            })
        user_msg["content"].append({
                "type": "text",
                # prompt
                "text": prompt
            })
    else:
        history_msg = st.session_state.messages
        user_msg["content"].append({
                "type": "text",
                "text": prompt
            })

    #Add uploads
    if st.session_state.uploaded_file is not None:
        if "image" in st.session_state.uploaded_file.type:
            image = Image.open(st.session_state.uploaded_file)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_b64_str = base64.b64encode(buffered.getvalue()).decode()
            st.session_state.upload_img = f"data:image/jpeg;base64,{img_b64_str}"
            
            user_msg["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": st.session_state.upload_img
                }
            })
            
            st.session_state.upload_img = None
        elif "video" in st.session_state.uploaded_file.type:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                   file_id, mimetype = video_to_url(st.session_state.uploaded_file.getvalue(), "mp4")
                   video_url = compose_media_url(file_id, ".mp4")
                   video_url_b64 = video_url_to_base64(video_url)
                   user_msg["content"].append({
                        "type": "video_url",
                        "video_url": {"url": video_url_b64},
                        "max_pixels": DEFAULT_MAX_PIXELS_TO_VLM,
                        "fps": 1
                   })

    if st.session_state.uploaded_url:
        image = Image.open(requests.get(st.session_state.uploaded_url, stream=True, timeout=3000).raw)
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_b64_str = base64.b64encode(buffered.getvalue()).decode()
        st.session_state.upload_img = f"data:image/jpeg;base64,{img_b64_str}"
        user_msg["content"].append({
            "type": "image_url",
            "image_url": {
                "url": st.session_state.upload_img
            }
        })
        st.session_state.upload_img = None

    # add selected
    if st.session_state.selectbox_keys_cache != st.session_state.selectbox_keys:
        selected_medias = []
        for option, selected in st.session_state.selectbox_keys.items():
            if selected and not st.session_state.selectbox_keys_cache.get(option):
                # Keys are f"{index}v"/f"{index}i"; strip the type suffix rather
                # than the first character so indexes past 9 still resolve.
                selected_medias.append(st.session_state.data[int(option[:-1])])
        st.session_state.selectbox_keys_cache = copy.deepcopy(st.session_state.selectbox_keys)
        for selected_media in selected_medias:
            meta = selected_media["meta"]
            file_path = meta.get("file_path", "")
            if is_video_meta(meta):
                video_bytes = fetch_media_bytes(meta)
                if video_bytes is None:
                    logger.error("Unable to read selected video %s", file_path)
                    continue
                file_id, mimetype = video_to_url(video_bytes, "mp4")
                video_url = compose_media_url(file_id, ".mp4")
                video_url_b64 = video_url_to_base64(video_url)
                user_msg["content"].append({
                    "type": "video_url",
                    "video_url": {
                        "url": video_url_b64
                    },
                    "max_pixels": DEFAULT_MAX_PIXELS_TO_VLM,
                    "fps": 1
                })
            else:
                image_bytes = fetch_media_bytes(meta)
                if image_bytes is None:
                    logger.error("Unable to read selected image %s", file_path)
                    continue
                image = Image.open(BytesIO(image_bytes))
                file_id, mimetype  = image_to_url(image, "auto", width=480)
                _, extension = os.path.splitext(file_path or meta.get("filename", ""))
                image_url = compose_media_url(file_id, extension)
                img_b64_str = encode_base64_content_from_url(image_url)
                image_url_b64 = f"data:image/jpeg;base64,{img_b64_str}"
                user_msg["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url_b64
                    }
                })
        

    vqa_msg = []
    if len(history_msg) == 0:
        vqa_msg = [system_msg, user_msg]
    else:
        if len(user_msg["content"]) > 0:
            history_msg.append(user_msg)
        vqa_msg = history_msg

    return vqa_msg

def send_update_db_request():
    """Ingest a host directory through the dataprep microservice.

    Submits an asynchronous batch job for the directory and blocks until the job
    reaches a terminal state, so the caller keeps the simple "update finished"
    semantics the UI expects. ``store_copy`` is disabled: the media directory is
    already shared with the service, so the files are embedded in place and the
    origin path is recorded as ``source_path`` for rendering.
    """
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/media/ingest-dir"

    payload = {
        "dir_path": helper_map2ingest(st.session_state["kfilePath"]),
        "bucket_name": DATAPREP_BUCKET_NAME,
        "frame_interval": DATA_INGEST_FRAME_INTERVAL,
        "enable_object_detection": DATA_INGEST_WITH_DETECT,
        "store_copy": False,
        "recursive": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        submission = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")
        return {"status": "error", "message": str(e)}

    job_id = submission.get("job_id")
    accepted = submission.get("accepted", 0)
    if not job_id:
        return submission

    logger.info(f"Ingestion job {job_id} accepted ({accepted} item(s))")
    if accepted == 0:
        # Everything in the directory was already ingested (duplicate policy).
        return {
            "status": "completed",
            "accepted": 0,
            "message": submission.get("message", "Nothing new to ingest."),
        }

    result = wait_for_ingest_job(job_id)
    result["accepted"] = accepted
    result["message"] = submission.get("message", "")
    return result


def wait_for_ingest_job(job_id: str):
    """Poll a dataprep batch job until it reaches a terminal state."""
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/media/jobs/{job_id}"
    deadline = time.time() + DATAPREP_JOB_TIMEOUT
    status = {}
    consecutive_errors = 0

    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            status = response.json()
            consecutive_errors = 0
        except requests.exceptions.RequestException as e:
            consecutive_errors += 1
            logger.warning(
                f"Error polling ingestion job {job_id} "
                f"({consecutive_errors}/{DATAPREP_JOB_POLL_RETRIES}): {e}"
            )
            if consecutive_errors >= DATAPREP_JOB_POLL_RETRIES:
                logger.error(f"Giving up polling ingestion job {job_id}: {e}")
                return {"status": "error", "message": str(e)}
            time.sleep(DATAPREP_JOB_POLL_INTERVAL)
            continue

        if status.get("state") in ("completed", "completed_with_errors", "failed", "cancelled"):
            break
        time.sleep(DATAPREP_JOB_POLL_INTERVAL)
    else:
        return {"status": "error", "message": f"Ingestion job {job_id} timed out"}

    errors = [
        f"{item.get('identifier')}: {item.get('message')}"
        for item in status.get("items", [])
        if item.get("status") == "error"
    ]
    result = {
        "status": status.get("state"),
        "job_id": job_id,
        "total": status.get("total"),
        "completed": status.get("completed"),
        "failed": status.get("failed"),
    }
    if errors:
        result["errors"] = "; ".join(errors)
    logger.info(f"Ingestion job {job_id} finished: {result}")
    return result

def send_clear_db_request():
    """Clear the configured dataprep bucket (embeddings and any stored objects)."""
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/media/{DATAPREP_BUCKET_NAME}"
    result = {}
    try:
        response = requests.delete(url, timeout=120)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Response: {result}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")
        result = {"status": "error", "message": str(e)}

    return result

def send_db_info_request():
    """Report the dataprep service status (embedding model, devices, backends)."""
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/health"
    result = {}
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        health = response.json()
        result = {
            "status": health.get("status", "unknown"),
            "embedding_model": health.get("model_name") or EMBEDDING_MODEL_NAME,
            "embedding_device": health.get("embedding_device", "unknown"),
            "detection_model": health.get("detection_model", "unknown"),
            "vector_db": health.get("vectordb_backend", "unknown"),
            "vector_db_status": health.get("vectordb_status", "unknown"),
            "bucket": health.get("default_bucket_name", DATAPREP_BUCKET_NAME),
        }
        logger.info(f"Response: {result}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")
        result = {"status": "error", "message": str(e)}

    return result

def is_english(text):
    for char in text:
        if not char.isascii():
            return False
    return True

def is_bad_string(s):
    # Define a regular expression pattern for non-printable characters
    non_printable_pattern = re.compile(f'[^{re.escape(string.printable)}]')
    
    # Check for non-printable characters
    if non_printable_pattern.search(s):
        return True
    
    # Check for malformed characters
    for char in s:
        try:
            unicodedata.name(char)
        except ValueError:
            return True
    
    return False

def is_symlink(path):
    return os.path.islink(path)

def initialize_session_state():
    if 'initialized' not in st.session_state:
        st.session_state.data = None
        st.session_state.result_per_row = SHOW_RESULT_PER_ROW
        
        st.session_state.selectbox_keys = {}
        st.session_state.selectbox_keys_cache = {}
        st.session_state.messages = []
        st.session_state.selected_videos_len = 0
        st.session_state.selected_images_len = 0
        st.session_state.de_duplicate = False
        st.session_state.uploader_key = 100
        st.session_state.uploader_key_cache = 100
        st.session_state.uploader_url_key = 200
        st.session_state.uploader_url_key_cache = 200
        st.session_state.uploaded_file = None
        st.session_state.uploaded_url = None
        st.session_state.upload_img = None
        st.session_state.is_query = True
        st.session_state.vqa_prompt_key = 700
        st.session_state.query_key = 900
        st.session_state.start_time = None
        st.session_state.end_time = None
        st.session_state.last_time = None
        st.session_state.threshold = None
        st.session_state.client = OpenAI(
                                    api_key="EMPTY",
                                    base_url=BACKEND_VQA_BASE_URL + "/v1",
                                )
        st.session_state.latest_log = ""
        st.session_state.file_for_search = None
        st.session_state.initialized = True

def query_submit():
    # Ensure only one of ktext or file_for_search is provided
    if st.session_state["ktext"] and st.session_state.file_for_search:
        logger.warning("Both text and image provided for search; only one is supported")
        query_display.error("Only one of 'Prompt' or 'Uploaded File' can be used for the query. Please provide only one.")
        return
    if not st.session_state["ktext"] and not st.session_state.file_for_search:
        query_display.info("Need either a query text or uploaded file for the search.")
        return

    if st.session_state.file_for_search is not None:
        # Handle the uploaded file for search
        uploaded_file = st.session_state.file_for_search
        try:
            image = Image.open(uploaded_file)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_b64_str = base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            query_display.error(f"Error processing uploaded file: {e}")
            return

    else:
        if not st.session_state["ktext"]:
            return

        if len(st.session_state["ktext"]) > PROMPT_LENGTH_LIMIT:
            query_display.error(f"Please enter a prompt with less than {PROMPT_LENGTH_LIMIT} characters!")
            return
        if not is_english(st.session_state["ktext"]) and "cn" not in EMBEDDING_MODEL_NAME.lower():
            query_display.error("Current embedding model only supports English!")
            return
        if is_english(st.session_state["ktext"]) and is_bad_string(st.session_state["ktext"]):
            query_display.error("Please enter a valid prompt!")
            return
    
    for option, selected in st.session_state.selectbox_keys.items():
        st.session_state[option] = False
    st.session_state.selectbox_keys_cache = {}
    if st.session_state.is_query:
        st.toast("History has been cleared!")
        st.session_state.selectbox_keys = {}
        if st.session_state.uploaded_file is not None:
            # Clear the file uploader
            st.session_state.uploader_key += 1
        st.session_state.messages = []
        st.session_state.is_query = True
        st.session_state.selected_videos_len = 0
        st.session_state.selected_images_len = 0
    
    where_clauses = []
    if st.session_state["kCamera"]:
        where_clauses.append({"field": METADATA_CAMERA_FIELD, "op": "eq", "value": st.session_state["kCamera"]})
    if st.session_state["f_s_time"]:
        s_time = st.session_state["f_s_time"]
        where_clauses.append({"field": METADATA_DATE_FIELD, "op": "gte", "value": int(s_time.strftime("%Y%m%d"))})
    if st.session_state["f_e_time"]:
        e_time = st.session_state["f_e_time"]
        where_clauses.append({"field": METADATA_DATE_FIELD, "op": "lte", "value": int(e_time.strftime("%Y%m%d"))})

    where = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"all": where_clauses}

    if st.session_state.file_for_search is not None:
        data = send_query_request(image_base64=img_b64_str, k=st.session_state["kk"], where=where)
    else:
        data = send_query_request(text=st.session_state["ktext"], k=st.session_state["kk"], where=where)
    data = filter_output(data, st.session_state.de_duplicate)
    logger.info(f"Search results: {data}")

    response_text = ["\n".join(f"{key}: {value}" for key, value in hit.items()) for hit in data]
    st.session_state.latest_log = response_text

    for i in range(len(data)):
        if data[i]["meta"]["file_path"] != "":
            data[i]["meta"]["file_path"] = helper_map2container(data[i]["meta"]["file_path"])
    st.session_state.data = data

def update_db():
    with st.spinner("Updating...", show_time=True):
        response = send_update_db_request()
        response_text = "\n".join(f"{key}: {value}" for key, value in response.items())

    st.session_state.latest_log = response_text

def clear_db():
    response = send_clear_db_request()
    response_text = "\n".join(f"{key}: {value}" for key, value in response.items())

    st.session_state.latest_log = response_text

@st.dialog("Info")
def vote():
    st.write(f"Backend dataprep service at {BACKEND_DATAPREP_BASE_URL}")
    st.write(f"Backend retriever service at {BACKEND_SEARCH_BASE_URL}")
    st.write(f"Backend vqa service at {BACKEND_VQA_BASE_URL}")
    db_info = send_db_info_request()
    if db_info:
        st.write("Dataprep service info:")
        for key, value in db_info.items():
            st.write(f"{key.replace('_', ' ').capitalize()}: {value}")

    if st.session_state.latest_log:
        st.write("Latest response:")
        latest_log = st.session_state.latest_log
        if len(st.session_state.latest_log) > 1000:
            latest_log = st.session_state.latest_log[:1000] + "..."
        st.write(latest_log)
    
def checkbox_change():
    st.session_state.is_query = False
    v_num = 0
    i_num = 0
    for key, value in st.session_state.selectbox_keys.items():
        if "i" in key and st.session_state[key]:
            i_num += 1
        elif "v" in key and st.session_state[key]:
            v_num += 1
    st.session_state.selected_videos_len = v_num
    st.session_state.selected_images_len = i_num

def show_media():
    if st.session_state.data:
        columns_per_row = st.session_state.result_per_row
        num_rows = (len(st.session_state.data) + columns_per_row - 1) // columns_per_row
        keys = {}
        
        for i in range(num_rows):
            row_cols = query_display.columns(columns_per_row,gap="small")
            for j in range(min(columns_per_row, len(st.session_state.data) - i * columns_per_row)):
                index = i * columns_per_row + j

                with row_cols[j]:
                    col1, col2 = st.columns([5,1])
                    target = st.session_state.data[index]
                    target_path = target["meta"]["file_path"]
                    media_url = target["meta"].get("media_url", "")
                    # Prefer the dataprep streaming URL: the browser fetches it
                    # directly with Range requests, so seeking works and the file
                    # never has to be read into this app's memory. The bind-mounted
                    # path stays as a fallback for producers without a media URL.
                    playable = media_url or (target_path if os.path.exists(target_path) else "")
                    if "video" in target["meta"]["type"]:
                        if not playable:
                            st.error(f"{target_path} is invalid")
                            continue
                        if f"{index}v" not in st.session_state.selectbox_keys:
                            st.session_state.selectbox_keys[f"{index}v"] = False
                        st.session_state.selectbox_keys[f"{index}v"] = col2.checkbox(
                            "Select video result",
                            key=f"{index}v",
                            on_change=checkbox_change,
                            label_visibility="collapsed",
                        )
                        if media_url:
                            st.video(media_url, start_time=int(target["meta"]["video_pin_second"]))
                        else:
                            with open(target_path, "rb") as video_file:
                                st.video(
                                    video_file.read(),
                                    start_time=int(target["meta"]["video_pin_second"]),
                                )
                    else:
                        if not playable:
                            st.error(f"{target_path} is invalid")
                            continue

                        if f"{index}i" not in st.session_state.selectbox_keys:
                            st.session_state.selectbox_keys[f"{index}i"] = False
                        st.session_state.selectbox_keys[f"{index}i"] = col2.checkbox(
                            "Select image result",
                            key=f"{index}i",
                            on_change=checkbox_change,
                            label_visibility="collapsed",
                        )
                        st.image(media_url or Image.open(target_path), width=480)
                        
                    css = f"""<style>
                                .st-key-media_display .e6rk8up0:nth-of-type({i+1}) .e6rk8up2:nth-of-type({j+1}){{
                                        padding: 5px;
                                        background-color: #F0F2F6;
                                    }}
                            </style>"""
                    st.markdown(css, unsafe_allow_html=True)
        st.session_state.is_query = True

def call_vqa():
    st.session_state.start_time = time.time()
    vqa_msg = get_vqa_msg(vqa_prompt)

    st.session_state.messages = vqa_msg

    with history.chat_message("user"):
        message = st.session_state.messages[-1]
        for contents in message.get("content"):
            if contents.get("type") == "text":
                st.write(contents.get("text"))
            if st.session_state.uploaded_file:
                if "image" in st.session_state.uploaded_file.type:
                    st.image(st.session_state.uploaded_file, width=480)
                if "video" in st.session_state.uploaded_file.type:
                    st.video(st.session_state.uploaded_file)
                break
            else:
                if contents.get("type") == "image_url":
                    if contents.get("image_url").get("url"):
                        url = contents.get("image_url").get("url")
                        st.image(url, width=480)
                if contents.get("type") == "video_url":
                    if contents.get("video_url"):
                        video_url = contents.get("video_url").get("url")
                        st.video(video_url)

    logger.info(f"VQA request message: {vqa_msg}")
    stream = st.session_state.client.chat.completions.create(
                model=VLM_MODEL_NAME,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                max_completion_tokens=1000,
                stream=True,
            )


    with history.chat_message("assistant"):
        response = st.write_stream(stream)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.latest_log = response
    # Clear the file
    if st.session_state.uploaded_file is not None:
        st.session_state.uploader_key += 1
    if st.session_state.uploader_url_key is not None:
        st.session_state.uploader_url_key += 1
    st.session_state.is_query = False

if __name__ == '__main__':
    st.set_page_config(
        page_title="Vision Large Model Based Multi-Modal Image Searching",
        layout="wide",    # 'wide' or 'centered'
    )
    html_code = """
    <div class="fixed-title">
        <h1>VisualSearch & QA</h1>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

    initialize_session_state()

    if is_symlink(Path("css.css")) or not os.path.exists("css.css"):
        logger.error(f"css.css is invalid")
        st.error(f"css.css is invalid")
        st.stop()
        sys.exit(1)
    with open("css.css", "r") as css_file:
        css_content = css_file.read()
    background_color_css = f"""<style>{css_content} </style>"""
    st.markdown(background_color_css, unsafe_allow_html=True)

    text = ""
    file_path = ""
    k = DEFAULT_NUM_SEARCH_RESULTS

    with st.container(key="form",border = False):
        col1, col2, col3, col4= st.columns([0.65,1.2,1.8,1.6])
        with col1.container(height=100):
            k =  st.number_input('max output number', min_value=1, max_value=MAX_MAX_NUM_SEARCH_RESULTS, value=k, key="kk", placeholder=f"0~{MAX_MAX_NUM_SEARCH_RESULTS}")
        with col2.container(height=100):
            col5, col6 = st.columns([1,1])
            with col5.container():
                st.write("de-duplicate")
                st.write("threshold (sec):")

            with col6.container():
                st.session_state.de_duplicate = st.checkbox(
                    "Enable deduplication",
                    label_visibility="collapsed",
                    key="kded",
                )
                st.session_state.threshold = st.number_input(
                    "Deduplication threshold",
                    label_visibility="collapsed",
                    format="%0.1f",
                    value=5.0,
                    step=0.1,
                    key="kthreshold",
                )
        with col3.container(height=100):
            file_path = st.text_input("file directory on host",value=file_path,key="kfilePath")
        with col4.container(height=100,key = "bt"):
            with st.container():
                st.write("")
            col4_col1, col4_col2, col4_col3= st.columns([1.5,1.1,1.3])
            with col4_col1.container():
                update_db=st.button("UpdateDB",on_click = update_db, key= "kupdate_db")

            with col4_col2.container():
                clear_db=col4_col2.button("ClearDB",on_click = clear_db, key= "kclear_db")

            def showInfo():
                vote()
            with col4_col3.container():
                showInfo_bd=col4_col3.button("showInfo",on_click = showInfo, key= "kshowInfo")


        with st.container(height=200):
            col_prompt, col_or, col_file_uploader, col_preview, col_clear_file = st.columns([14, 1, 10, 10, 2])  # Adjust column widths
            with col_prompt:
                prompt_text = st.text_input("Query in text", value=text, key="ktext")
            with col_or:
                st.text("OR")
            with col_file_uploader:
                st.session_state.file_for_search = st.file_uploader(
                    "Upload image for search",
                    key=f"search_file_uploader_{st.session_state.uploader_key}"
                )
            with col_preview:
                preview_placeholder = st.empty() 
                if st.session_state.file_for_search:
                    try:
                        image = Image.open(st.session_state.file_for_search)
                        preview_placeholder.image(image, caption="Preview")
                    except Exception as e:
                        preview_placeholder.error(f"Error displaying preview: {e}")
                else:
                    preview_placeholder.info("Image preview")
            with col_clear_file:
                if st.button("Clear File", key="clear_file_button"):
                    st.session_state.file_for_search = None  # Clear the uploaded file
                    st.session_state.uploader_key += 1  # Increment the key to reset the file uploader
            
        col7,col8,col9 = st.columns([1.2,2.1,3.8])

        with col7.container():
            col8_col1,col8_col2 = st.columns([1.1,2])
            with col8_col1.container():
                st.write("Camera:")
            st.session_state.Camera = col8_col2.text_input(
                "Camera filter",
                label_visibility="collapsed",
                key="kCamera",
            )
        with col8.container():
            col9_col1,col9_col2,col9_col3,col9_col4 = st.columns([1.3, 1.5, 0.4, 1.5])
            col9_col1.write("Timestamp:")
            st.session_state.f_s_time = col9_col2.date_input(
                "Start date filter",
                value=None,
                label_visibility="collapsed",
                key="kf_s_time",
            )
            col9_col3.write("to")
            st.session_state.f_e_time = col9_col4.date_input(
                "End date filter",
                value=None,
                label_visibility="collapsed",
                key="kf_e_time",
            )
        with col9.container(key = "search"):
            query = st.button("Search", use_container_width=True, on_click=query_submit, key="kSearch")
    query_display = st.container(height=520,key="media_display")
    show_media()
    st.info(f"You have selected {st.session_state.selected_images_len} image(s) and {st.session_state.selected_videos_len} video(s),which will be used as the input of VQA!")


    with st.sidebar:
        def upload_change():
            st.session_state.is_query = False
            st.session_state.uploader_url_key += 1
        def vqa_prompt_submit():
            st.session_state.is_query = False
        def uploader_url_change():
            st.session_state.uploader_key += 1
        history = st.container(height = 600,key = "history")
        c_model_name,c_clear = st.columns([11,6])
        vqa_prompt = st.chat_input("Say something", key = st.session_state.vqa_prompt_key,on_submit = vqa_prompt_submit)
        c_model_name = c_model_name.write(f"Current Model:{VLM_MODEL_NAME}")
        clear = c_clear.button("clear")

        st.session_state.uploaded_file = st.file_uploader(
            "Upload Image/Video",
            key=st.session_state.uploader_key,
            on_change = upload_change
        )

        st.session_state.uploaded_url = st.text_input("Import from URL",on_change = uploader_url_change,key = st.session_state.uploader_url_key)
        if st.session_state.uploaded_url:
            st.image(st.session_state.uploaded_url, width=480)
        elif st.session_state.uploaded_file and  "image" in st.session_state.uploaded_file.type:
            st.image(st.session_state.uploaded_file, width=480)


        if clear:
            st.session_state.messages = []
            if st.session_state.uploaded_file is not None:
                # Clear the file uploader
                st.session_state.uploader_key += 1
            st.session_state.selectbox_keys_cache = {}

        # HISTORY
        for message in st.session_state.messages:
            if message["role"] == ROLE_SYSTEM:
                continue
            with history.chat_message(message["role"]):
                if message.get("role") == ROLE_USER:
                    for contents in message.get("content"):
                        if contents.get("type") == "image_url":
                            if contents.get("image_url").get("url"):
                                url = contents.get("image_url").get("url")
                                st.image(url, width=480)
                        if contents.get("type") == "video_url":
                            if contents.get("video_url"):
                                video_url = contents.get("video_url").get("url")
                                st.video(video_url)

                        if contents.get("type") == "text":
                            st.write(contents.get("text"))
                elif message.get("role") == ROLE_ASSISTANT:
                    st.write(message.get("content"))

        if vqa_prompt:
            call_vqa()

        if st.session_state.messages:
            end_time = time.time()
            if st.session_state.start_time and vqa_prompt:
                st.session_state.last_time = end_time - st.session_state.start_time
            logger.debug(f"st.session_state.last_time,{st.session_state.last_time}")
            if st.session_state.last_time is not None:
                html_code = f"""
                   <p style="text-align: right; font-weight: bold;">End to End Time:{round(st.session_state.last_time,2)} s</p>
                """
                history.markdown(html_code, unsafe_allow_html=True)
