# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import re
import os
from streamlit.testing.v1 import AppTest

from ut_utils import copy_dataset

# Cluster deployments run far slower than a local compose stack, so allow the
# timeout to be raised via APP_TEST_TIMEOUT without editing the suite.
APP_TIMEOUT = max(int(os.environ.get("APP_TEST_TIMEOUT", "0")), 300)

HOST_DATA_PATH = os.environ.get("HOST_DATA_PATH", "/home/user/data")
HOST_DATA_PATH_COPY = HOST_DATA_PATH
HOST_DATA_PATH = os.path.join(HOST_DATA_PATH, "DAVIS", "subset")
HOST_DATA_PATH_COPY = os.path.join(HOST_DATA_PATH_COPY, "DAVIS", "subset_copy")
MOUNT_DATA_PATH = "/home/user/data/DAVIS/subset"
MOUNT_DATA_PATH_COPY = "/home/user/data/DAVIS/subset_copy"

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def helper_map2container(file_path: str):
    if file_path.startswith(HOST_DATA_PATH):
        return file_path.replace(HOST_DATA_PATH, MOUNT_DATA_PATH)
    else:
        return file_path
    
def _log_field(field):
    """Read a `field: value` entry out of the UI's latest response log."""
    match = re.search(rf"^{field}: (.+)$", at.session_state.latest_log, re.MULTILINE)
    return match.group(1).strip() if match else None


def test_data_ingestion():
    # Start from a known state, then ingest the demo dataset.
    at.button(key="kclear_db").click().run()

    at.text_input(key="kfilePath").input(HOST_DATA_PATH)
    at.button(key="kupdate_db").click().run()
    assert _log_field("status") == "completed", f"Ingestion failed: {at.session_state.latest_log}"
    total = int(_log_field("total"))
    assert total > 0
    assert int(_log_field("completed")) == total, f"Not every item was ingested: {at.session_state.latest_log}"

    # Re-ingesting the same directory is a no-op: the dataprep service skips
    # files whose content it has already embedded.
    at.button(key="kupdate_db").click().run()
    assert int(_log_field("accepted")) == 0, f"Re-ingest was not deduplicated: {at.session_state.latest_log}"

    # The same content under a different path is deduplicated as well.
    copy_dataset(helper_map2container(HOST_DATA_PATH), helper_map2container(HOST_DATA_PATH_COPY))
    at.text_input(key="kfilePath").input(HOST_DATA_PATH_COPY)
    at.button(key="kupdate_db").click().run()
    assert int(_log_field("accepted")) == 0, f"Copy was not deduplicated: {at.session_state.latest_log}"

    # Clearing the DB succeeds, and the dataset can be ingested again afterwards.
    at.button(key="kclear_db").click().run()
    assert _log_field("status") == "success", f"Clear DB failed: {at.session_state.latest_log}"

    at.text_input(key="kfilePath").input(HOST_DATA_PATH)
    at.button(key="kupdate_db").click().run()
    assert _log_field("status") == "completed", f"Ingestion failed: {at.session_state.latest_log}"
    assert int(_log_field("total")) == total
