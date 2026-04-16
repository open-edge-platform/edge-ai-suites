#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import time
from typing import Any

class BizCode:
    SUCCESS = 20000
    BAD_REQUEST = 40000
    AUTH_FAILED = 40001
    FILE_ALREADY_EXISTS = 40901
    FILE_TYPE_ERROR = 50001
    TASK_NOT_FOUND = 50002
    PROCESS_FAILED = 50003

def resp_200(data: Any = None, message: str = "Success", code: int = BizCode.SUCCESS, **kwargs) -> dict:
    """
    1. resp_200(data={"id": 1})
    2. resp_200(**resp_task_not_found())
    """
    if isinstance(data, dict) and ("is_biz_error" in data or "code" in data):
        biz_code = data.get("code", BizCode.BAD_REQUEST)
        if biz_code != BizCode.SUCCESS:
            code = biz_code
            message = data.get("message", message)
            data = data.get("data", {})

    return {
        "code": code,
        "data": data if data is not None else {},
        "message": message,
        "timestamp": int(time.time())
    }

def resp_biz_error(code: int, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "data": {},
        "is_biz_error": True
    }

def fail_task_not_found():
    return resp_biz_error(BizCode.TASK_NOT_FOUND, "Task ID does not exist or has expired")

def fail_process_failed(detail: str = ""):
    msg = f"Internal processing error: {detail}" if detail else "Internal processing error"
    return resp_biz_error(BizCode.PROCESS_FAILED, msg)

def fail_processing():
    return resp_biz_error(BizCode.BAD_REQUEST, "Task is still processing")