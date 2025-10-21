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

from utils import image_to_url, video_to_url

PROMPT_LENGTH_LIMIT = 1024
ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"

# Get environment variables
BACKEND_VQA_BASE_URL = os.getenv("BACKEND_VQA_BASE_URL", "http://localhost:8399")
BACKEND_SEARCH_BASE_URL = os.getenv("BACKEND_SEARCH_BASE_URL", "http://localhost:7770")
BACKEND_DATAPREP_BASE_URL = os.getenv("BACKEND_DATAPREP_BASE_URL", "http://localhost:9990")

VCLIP_MODEL = os.getenv("VCLIP_MODEL", "openai/clip-vit-base-patch32")
VLM_MODEL_NAME=os.getenv("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")

DATA_INGEST_WITH_DETECT = os.getenv("DATA_INGEST_WITH_DETECT", "True").lower() == "true"

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


def send_query_request(text: str = "", image_base64: str = "", k: int = 10, filter: dict = {}):
    url = f"{BACKEND_SEARCH_BASE_URL}/v1/retrieval" 

    if text:
        logger.info(f"Querying {text}")
        payload = {
            "query": text,
            "filter": filter,  
            "max_num_results": k
        }
    elif image_base64:
        logger.info(f"Querying image")
        payload = {
            "image_base64": image_base64,
            "filter": filter,  
            "max_num_results": k
        }
    else:
        logger.error("No query or image provided")
        return None

    results = {}

    try:
        response = requests.post(url, json=payload, timeout=10)  # Set a timeout to avoid hanging
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response JSON
        results = response.json()["results"]

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")
    
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
                selected_medias.append(st.session_state.data[int(option[0:1])])
        st.session_state.selectbox_keys_cache = copy.deepcopy(st.session_state.selectbox_keys)
        for selected_media in selected_medias:
            file_path = selected_media["meta"]["file_path"]            
            if file_path.lower().endswith(('.mp4')):
                video_file = open(file_path, "rb")
                video_bytes = video_file.read()
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
                image = Image.open(file_path)
                file_id, mimetype  = image_to_url(image, "auto", width=480)
                _, extension = os.path.splitext(file_path)
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
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/ingest"  

    payload = {
        "file_dir": st.session_state["kfilePath"],
        "frame_extract_interval": 15,
        "do_detect_and_crop": DATA_INGEST_WITH_DETECT
    }

    result = {}

    try:
        response = requests.post(url, json=payload, timeout=10)  # Set a timeout to avoid hanging
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response JSON
        result = response.json()
        logger.info("Response:", result)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")

    return result

def send_clear_db_request():
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/delete_all"  
    result = {}
    try:
        response = requests.delete(url, timeout=10)  # Set a timeout to avoid hanging
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response JSON
        result = response.json()
        logger.info("Response:", result)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")

    return result

def send_db_info_request():
    url = f"{BACKEND_DATAPREP_BASE_URL}/v1/dataprep/info"  
    result = {}
    try:
        response = requests.get(url, timeout=10)  # Set a timeout to avoid hanging
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response JSON
        result = response.json()
        logger.info("Response:", result)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending request: {e}")

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
        if not is_english(st.session_state["ktext"]) and "cn" not in VCLIP_MODEL.lower():
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
    
    filters = {}
    if st.session_state["kCamera"]:
        filters["camera"] = st.session_state["kCamera"]
    if st.session_state["f_s_time"]:
        s_time = st.session_state["f_s_time"]
        filters["timestamp_start"] = int(s_time.strftime("%Y%m%d"))
    if st.session_state["f_e_time"]:
        e_time = st.session_state["f_e_time"]
        filters["timestamp_end"] = int(e_time.strftime("%Y%m%d"))

    if st.session_state.file_for_search is not None:
        data = send_query_request(image_base64=img_b64_str, k=st.session_state["kk"], filter=filters)
    else:
        data = send_query_request(text=st.session_state["ktext"], k=st.session_state["kk"], filter=filters)
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
        st.write("Vector DB info:")
        st.write(f"Local embedding model id: {db_info['model_id']}")
        st.write(f"device: {db_info['device']}")
        st.write(f"Number of processed files: {db_info['Number of processed files']}")

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
                    if "video" in target["meta"]["type"]:
                        if not os.path.exists(target_path):
                            st.error(f"{target_path} is invalid")
                            continue
                        video_file = open(target_path, "rb")
                        video_bytes = video_file.read()
                        if f"{index}v" not in st.session_state.selectbox_keys:
                            st.session_state.selectbox_keys[f"{index}v"] = False
                        st.session_state.selectbox_keys[f"{index}v"] = col2.checkbox("",key= f"{index}v",on_change=checkbox_change,label_visibility="visible")
                        st.video(video_bytes,start_time=int(target["meta"]["video_pin_second"]))
                    else:
                        if not os.path.exists(target_path):
                            st.error(f"{target_path} is invalid")
                            continue

                        if f"{index}i" not in st.session_state.selectbox_keys:
                            st.session_state.selectbox_keys[f"{index}i"] = False
                        st.session_state.selectbox_keys[f"{index}i"] = col2.checkbox("",key= f"{index}i",on_change=checkbox_change,label_visibility="visible")
                        image = Image.open(target_path)
                        st.image(image, width=480)
                        
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
                st.session_state.de_duplicate = st.checkbox("",label_visibility="visible", key = "kded")
                st.session_state.threshold = st.number_input("",label_visibility="visible", format="%0.1f", value=5.0, step=0.1, key="kthreshold")
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
            st.session_state.Camera = col8_col2.text_input("",label_visibility="visible",key = "kCamera")
        with col8.container():
            col9_col1,col9_col2,col9_col3,col9_col4 = st.columns([1.3, 1.5, 0.4, 1.5])
            col9_col1.write("Timestamp:")
            st.session_state.f_s_time = col9_col2.date_input("", value=None, label_visibility="visible",key="kf_s_time")
            col9_col3.write("to")
            st.session_state.f_e_time = col9_col4.date_input("", value=None, label_visibility="visible", key="kf_e_time")
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
            html_code = f"""
               <p style="text-align: right; font-weight: bold;">End to End Time:{round(st.session_state.last_time,2)} s</p>
            """
            history.markdown(html_code, unsafe_allow_html=True)

