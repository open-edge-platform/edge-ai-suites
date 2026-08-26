# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from streamlit.testing.v1 import AppTest

# Cluster deployments run far slower than a local compose stack, so allow the
# timeout to be raised via APP_TEST_TIMEOUT without editing the suite.
APP_TIMEOUT = max(int(os.environ.get("APP_TEST_TIMEOUT", "0")), 300)

HOST_DATA_PATH = os.environ.get("HOST_DATA_PATH", "/home/user/data")
HOST_DATA_PATH = os.path.join(HOST_DATA_PATH, "DAVIS", "subset")

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def test_video_search():
    at.text_input(key="kfilePath").input(HOST_DATA_PATH)
    at.button(key="kupdate_db").click().run()
    runs = {"rollercoaster": "rollercoaster", "monkeys": "monkeys-trees"}
    for k, v in runs.items():
        at.text_input(key="ktext").input(k)
        at.button(key="kSearch").click().run()
        assert len(at.session_state.latest_log) > 0, "No search results found."
        assert "video_pin_second" in at.session_state.latest_log[0], "No video pin second found in search results."