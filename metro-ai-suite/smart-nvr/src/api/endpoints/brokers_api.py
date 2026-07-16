# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter, HTTPException, Request

from model.broker import Broker
from service import redis_store, broker_manager

broker_router = APIRouter(prefix="/brokers", tags=["brokers"])


@broker_router.get("/")
async def list_brokers(request: Request):
    return await redis_store.get_brokers(request)


@broker_router.get("/{broker_id}")
async def get_broker(broker_id: str, request: Request):
    broker = await redis_store.get_broker(broker_id, request)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return broker


@broker_router.post("/")
async def create_broker(broker: Broker, request: Request):
    if await redis_store.get_broker(broker.id, request):
        raise HTTPException(status_code=400, detail="Broker ID already exists")
    await redis_store.save_broker(broker.id, broker.model_dump(), request)
    await broker_manager.start_broker(broker)
    await broker_manager.sync_yaml_from_redis(request)
    return {"message": "Broker added", "broker": broker}


@broker_router.put("/{broker_id}")
async def update_broker(broker_id: str, broker: Broker, request: Request):
    if broker.id != broker_id:
        raise HTTPException(status_code=400, detail="Broker ID mismatch")
    await redis_store.save_broker(broker_id, broker.model_dump(), request)
    await broker_manager.restart_broker(broker)
    await broker_manager.sync_yaml_from_redis(request)
    return {"message": "Broker updated", "broker": broker}


@broker_router.delete("/{broker_id}")
async def delete_broker(broker_id: str, request: Request):
    deleted = await redis_store.delete_broker(broker_id, request)
    if not deleted:
        raise HTTPException(status_code=404, detail="Broker not found")
    await broker_manager.stop_broker(broker_id)
    await broker_manager.sync_yaml_from_redis(request)
    return {"message": f"Broker {broker_id} deleted"}
