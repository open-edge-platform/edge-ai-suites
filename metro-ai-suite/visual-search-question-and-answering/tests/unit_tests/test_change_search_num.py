# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from streamlit.testing.v1 import AppTest

APP_TIMEOUT = 30

HOST_DATA_PATH = os.environ.get("HOST_DATA_PATH", "/home/user/data")
HOST_DATA_PATH = os.path.join(HOST_DATA_PATH, "DAVIS", "subset")

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def test_change_search_num():
    at.text_input(key="kfilePath").input(HOST_DATA_PATH)
    at.button(key="kupdate_db").click().run()

    default_number = at.number_input(key="kk").value
    at.text_input(key="ktext").input("car")
    at.button(key="kSearch").click().run()
    default_number_res = len(at.session_state.latest_log)

    for _ in range(10):
        at.number_input(key="kk").increment().run()

    increased_number = at.number_input(key="kk").value  
    at.text_input(key="ktext").input("car")
    at.button(key="kSearch").click().run()
    increased_number_res = len(at.session_state.latest_log)
    assert increased_number_res > default_number_res, f"Got {increased_number_res} for {increased_number} and {default_number_res} for {default_number}"

    for _ in range(15):
        at.number_input(key="kk").decrement().run()

    decreased_number = at.number_input(key="kk").value
    at.text_input(key="ktext").input("car")
    at.button(key="kSearch").click().run()
    decreased_number_res = len(at.session_state.latest_log)
    assert decreased_number_res < default_number_res, f"Got {decreased_number_res} for {decreased_number} and {default_number_res} for {default_number}"