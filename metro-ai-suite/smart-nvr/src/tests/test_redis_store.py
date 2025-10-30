# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for Redis store helper functions using a fake in-memory implementation."""
import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import service.redis_store as rs


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.sets = {"rules": set()}
        self.lists = {}

    # Key/Value
    async def set(self, k, v):
        self.store[k] = v

    async def get(self, k):
        return self.store.get(k)

    async def exists(self, k):
        return 1 if k in self.store else 0

    async def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)
            self.lists.pop(k, None)

    # Sets
    async def sadd(self, key, val):
        self.sets.setdefault(key, set()).add(val)

    async def smembers(self, key):
        return self.sets.get(key, set())

    async def srem(self, key, val):
        self.sets.get(key, set()).discard(val)

    # Lists
    async def rpush(self, key, val):
        self.lists.setdefault(key, []).append(val)

    async def lrange(self, key, start, end):
        data = self.lists.get(key, [])
        if end == -1:
            end = len(data)
        return data[start:end]


def make_request(fake):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis_client=fake)))


@pytest.mark.asyncio
async def test_add_rule_and_duplicate():
    fake = FakeRedis()
    req = make_request(fake)
    added = await rs.add_rule(req, 'r1', {'id':'r1','label':'L','action':'a'})
    assert added is True
    dup = await rs.add_rule(req, 'r1', {'id':'r1','label':'L','action':'a'})
    assert dup is False


@pytest.mark.asyncio
async def test_rule_storage_and_delete():
    fake = FakeRedis()
    req = make_request(fake)
    await rs.store_rule(req, 'r2', {'id':'r2','label':'X','action':'b'})
    got = await rs.get_rule(req, 'r2')
    assert got['label'] == 'X'
    rules = await rs.get_rules(req)
    assert any(r['id']=='r2' for r in rules)
    ok = await rs.delete_rule(req, 'r2')
    assert ok is True
    missing = await rs.delete_rule(req, 'r2')
    assert missing is False


@pytest.mark.asyncio
async def test_store_and_fetch_responses_and_summaries():
    fake = FakeRedis()
    req = make_request(fake)
    # Simulate saving responses/search results
    await rs.store_response('r3', {'summary_id':'s1','status':'ok'}, req)
    await rs.save_summary_id('r3','s1', req)
    await rs.save_summary_result('s1','result-json', req)
    # Search results
    await rs.save_search('r3', {'video_id':'vid1','message':'done'}, req)
    ids = await rs.get_summary_ids(req, 'r3')
    assert 's1' in ids
    summary_val = await rs.get_summary_result(req, 's1')
    assert summary_val == 'result-json'
    search_results = await rs.get_search_results_by_rule('r3', req)
    assert search_results[0]['video_id'] == 'vid1'


@pytest.mark.asyncio
async def test_camera_watcher_mapping_store_load():
    fake = FakeRedis()
    req = make_request(fake)
    await rs.save_camera_watcher_mapping({'garage':True}, req)
    data = await rs.load_camera_watcher_mapping(req)
    assert data == {'garage':True}


@pytest.mark.asyncio
async def test_get_search_results_error_path(monkeypatch):
    class ExplodingRedis(FakeRedis):
        async def lrange(self, key, start, end):
            raise Exception('boom')
    fake = ExplodingRedis()
    req = make_request(fake)
    # Should swallow error and return []
    results = await rs.get_search_results_by_rule('rX', req)
    assert results == []