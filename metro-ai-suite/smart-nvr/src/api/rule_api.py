# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from service import redis_store

app = FastAPI()


class Rule(BaseModel):
    id: str
    label: str
    action: str
    camera: str | None = None


@app.post("/rules/")
async def add_rule(rule: Rule):
    success = await redis_store.add_rule(rule.id, rule.dict())
    if not success:
        raise HTTPException(status_code=400, detail="Rule ID already exists")
    return {"message": "Rule added", "rule": rule}


@app.get("/rules/")
async def list_rules():
    return await redis_store.get_rules()


@app.get("/rules/{rule_id}")
async def get_rule(rule_id: str):
    rule = await redis_store.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@app.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    deleted = await redis_store.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": f"Rule {rule_id} deleted"}
