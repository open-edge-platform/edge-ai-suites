# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import re
import os
import time
import datetime
from streamlit.testing.v1 import AppTest

from ut_utils import generate_fake_meta, remove_fake_meta_files

APP_TIMEOUT = 300

Query_list = {"deer": "deer",
"violin": "guitar-violin",
"workout": "gym", 
"helicopter": "helicopter", 
"carousel in a park": "carousel"
}

HOST_DATA_PATH = os.environ.get("HOST_DATA_PATH", "/home/user/data")
HOST_DATA_PATH = os.path.join(HOST_DATA_PATH, "DAVIS", "subset")
MOUNT_DATA_PATH = "/home/user/data/DAVIS/subset"

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def helper_map2container(file_path: str):
    if file_path.startswith(HOST_DATA_PATH):
        return file_path.replace(HOST_DATA_PATH, MOUNT_DATA_PATH)
    else:
        return file_path
    
def helper_ingest_data(file_path: str):
    at.button(key="kclear_db").click().run()
    at.text_input(key="kfilePath").input(file_path)
    at.button(key="kupdate_db").click().run()
    time.sleep(5)

def test_filter_search():
    generate_fake_meta(helper_map2container(HOST_DATA_PATH))
    helper_ingest_data(HOST_DATA_PATH)
    for k, v in Query_list.items():
        # full search
        at.text_input(key="ktext").input(k)
        at.button(key="kSearch").click().run()
        assert len(at.session_state.latest_log) > 0, "No search results found."

        # get unique camera label and timestamp
        match = re.search(r"'camera': '([^']+)'", at.session_state.latest_log[0])
        camera = match.group(1)

        match = re.search(r"'timestamp': (\d+)", at.session_state.latest_log[0])
        timestamp = int(match.group(1)) if match else None

        # filter search by camera label, should return 1 result because each fake meta has unique camera label
        at.text_input(key="kCamera").input(camera)
        at.button(key="kSearch").click().run()
        assert len(at.session_state.latest_log) == 1, f"Filter search by camera '{camera}' did not return expected result."

        # filter search by timestamp, should return 1 result
        at.date_input(key="kf_s_time").set_value(datetime.datetime.strptime(str(timestamp), "%Y%m%d").date())
        at.date_input(key="kf_e_time").set_value(datetime.datetime.strptime(str(timestamp), "%Y%m%d").date())
        at.button(key="kSearch").click().run()
        assert len(at.session_state.latest_log) == 1, f"Filter search by timestamp '{timestamp}' did not return expected result."

    # clean up
    remove_fake_meta_files(helper_map2container(HOST_DATA_PATH))
    helper_ingest_data(HOST_DATA_PATH)