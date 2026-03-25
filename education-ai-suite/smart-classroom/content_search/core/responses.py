import time
from typing import Any, Optional

def resp_200(data: Any, message: str = "Success") -> dict:
    return {
        "code": 20000,
        "data": data,
        "message": message,
        "timestamp": int(time.time())
    }