# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from streamlit.testing.v1 import AppTest

APP_TIMEOUT = 300

HOST_DATA_PATH = os.environ.get("HOST_DATA_PATH", "/home/user/data")
HOST_DATA_PATH = os.path.join(HOST_DATA_PATH, "DAVIS", "subset")

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def test_deduplicate_search():
    at.text_input(key="kfilePath").input(HOST_DATA_PATH)
    at.button(key="kupdate_db").click().run()
    # full search
    at.text_input(key="ktext").input("rollercoaster")
    at.button(key="kSearch").click().run()
    assert len(at.session_state.latest_log) > 0, "No search results found."
    full_number = len(at.session_state.latest_log)

    # deduplicate search
    at.checkbox(key="kded").check().run()
    at.text_input(key="ktext").input("rollercoaster")
    at.button(key="kSearch").click().run()
    assert len(at.session_state.latest_log) > 0, "No search results found after deduplication."
    dedup_number = len(at.session_state.latest_log)
    assert dedup_number < full_number, f"Deduplicated search returned {dedup_number} results, expected less than {full_number}."
