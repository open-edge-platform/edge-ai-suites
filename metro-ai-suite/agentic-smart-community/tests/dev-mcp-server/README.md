# MCP Server Development Tests

本目录包含 MCP Server 阶段性开发验证测试（Python）。

## 测试范围

| # | Test Case | 验证目标 |
|---|-----------|----------|
| 1 | DB CRUD | 数据库建表、Monitor/Alert/Task 增删改查正确 |
| 2 | Schema Customization | YAML 声明扩展字段后 DB 自动 ALTER TABLE |
| 3 | Tools (MCP call) | 通过 MCP Client SDK 调用每个 tool 并验证返回 |
| 4 | Events Webhook | POST /events 能正确创建 pending task |
| 5 | Video Worker 链路 | task-poller 取 pending task → VLM mock → 更新 DB |
| 6 | Rule Engine | 默认规则 + Python override 正确触发/不触发 alert |

## 运行方式

```bash
# 前置：确保项目已 build
cd <repo-root>
npm run build

# 运行全部测试
python tests/dev-mcp-server/run_all.py

# 运行单个测试
python tests/dev-mcp-server/test_db.py
python tests/dev-mcp-server/test_schema.py
python tests/dev-mcp-server/test_events_webhook.py
python tests/dev-mcp-server/test_rule_engine.py
python tests/dev-mcp-server/test_tools_mcp.py
```

## 前置条件

- Python 3.11+
- `npm install && npm run build` 已完成
- Node.js 18+ (用于启动 MCP Server 子进程)
- 不需要外部服务（VLM service 使用 mock）
