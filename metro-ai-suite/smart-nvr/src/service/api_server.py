# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import FastAPI
import uvicorn
from redis_store import get_responses

app = FastAPI()


@app.get("/results/{rule_id}")
async def fetch_results(rule_id: str):
    responses = await get_responses(rule_id)
    return [json.loads(r) for r in responses]


async def start_api():
    config = uvicorn.Config(app, host="0.0.0.0", port=5000)
    server = uvicorn.Server(config)
    await server.serve()
