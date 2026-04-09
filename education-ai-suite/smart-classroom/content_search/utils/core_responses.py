#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import time
from typing import Any, Dict

def resp_200(data: Any, message: str = "Success") -> dict:
    code = 20000
    if isinstance(data, dict):
        biz_code = data.get("code")
        if biz_code and biz_code != 20000:
            code = biz_code
            message = data.get("message", message)
            data = data.get("data", {})
        elif data.get("is_biz_error"):
            code = data.get("code", 40000)
            message = data.get("message", message)
            data = data.get("data", {})

    return {
        "code": code,
        "data": data,
        "message": message,
        "timestamp": int(time.time())
    }