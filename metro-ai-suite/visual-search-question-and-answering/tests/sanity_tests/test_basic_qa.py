# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from streamlit.testing.v1 import AppTest

APP_TIMEOUT = 30

VLM_MODEL_NAME=os.getenv("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")

at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
at.run()

def test_basic_qa():
    prompt = "who are you?"
    at.chat_input[0].set_value(prompt).run()
    assert at.chat_message[0].markdown[0].value == prompt
    assert at.chat_message[0].avatar == "user"
    if "Qwen" in VLM_MODEL_NAME:
        assert "Qwen" in at.session_state.latest_log
    at.chat_input[0].set_value("what is the capital of France").run()
    assert "Paris" in at.session_state.latest_log
    at.chat_input[0].set_value("calculate 2+3").run()
    assert "5" in at.session_state.latest_log
        