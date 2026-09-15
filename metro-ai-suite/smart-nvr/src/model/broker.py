# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel


class Broker(BaseModel):
    id: str
    name: str
    host: str
    port: int = 1883
    topic: str
    type: str = "scenescape"
    use_tls: bool = True
    throttle_interval: float = 2.0
    enabled: bool = True
