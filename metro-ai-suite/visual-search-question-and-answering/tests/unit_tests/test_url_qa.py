# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from streamlit.testing.v1 import AppTest

APP_TIMEOUT = 30

VLM_MODEL_NAME=os.getenv("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def test_url_qa():
    prompt = "what is in this image?"
    at.text_input(key="200").input("http://farm6.staticflickr.com/5268/5602445367_3504763978_z.jpg")
    at.chat_input[0].set_value(prompt).run()
    assert at.chat_message[0].markdown[0].value == prompt
    assert at.chat_message[0].avatar == "user"
    assert "girl" in at.session_state.latest_log or "teddy" in at.session_state.latest_log or "child" in at.session_state.latest_log