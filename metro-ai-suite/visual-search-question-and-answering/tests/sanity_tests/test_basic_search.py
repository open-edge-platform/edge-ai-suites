# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
from streamlit.testing.v1 import AppTest

APP_TIMEOUT = 30

Query_list = {"girl": "girl"}

HOST_DATA_PATH = "/home/user/data/sanity_tests"

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def test_basic_search():
    at.text_input(key="kfilePath").input(HOST_DATA_PATH)
    at.button(key="kupdate_db").click().run()
    for k, v in Query_list.items():
        at.text_input(key="ktext").input(k)
        at.button(key="kSearch").click().run()
        ret = False
        for i in range(len(at.session_state.latest_log)):
            if v in at.session_state.latest_log[i]:
                ret = True
                break
        assert ret, f"Search for '{k}' did not return expected result '{v}'."