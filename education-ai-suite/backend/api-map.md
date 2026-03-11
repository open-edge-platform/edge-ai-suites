# Edge AI Libraries Sample Applications API Map

本表用于前端对接与兼容性对照，来源于 `edge-ai-libraries/sample-applications`。

| 子项目 | 目录 | 用途 | Base Path / 服务 | API 列表 |
|---|---|---|---|---|
| chat-question-and-answer | `sample-applications/chat-question-and-answer/` | RAG 问答微服务（FastAPI） | `/v1/chatqna` | `GET /`（docs 入口），`GET /health`，`GET /model`，`POST /chat`（SSE 流式） |
| chat-question-and-answer-core | `sample-applications/chat-question-and-answer-core/` | 一体化 RAG 服务（FastAPI） | `/v1/chatqna` | `GET /health`，`GET /model`，`GET/POST/DELETE /documents`，`POST /chat`（SSE/非流式），OpenVINO: `GET /devices`、`GET /devices/{device}`，Ollama: `GET /ollama-models`、`GET /ollama-model` |
| document-summarization | `sample-applications/document-summarization/` | 文档摘要服务（FastAPI） | `http://localhost:8090/v1/docsum` | `GET /version`，`POST /summarize/`（multipart + SSE） |
| video-search-and-summarization (pipeline-manager) | `sample-applications/video-search-and-summarization/pipeline-manager/` | 视频检索与摘要编排（NestJS） | 服务根路径 | `GET /app/config`，`GET /app/features`，`GET /pipeline/frames`，`GET /pipeline/evam`，`GET /audio/models`，`GET/POST /videos`，`GET /videos/{videoId}`，`POST /videos/search-embeddings/{videoId}`，`GET /tags`，`DELETE /tags/{tagId}`，`GET /search`，`GET /search/watched`，`GET /search/{queryId}`，`POST /search`，`POST /search/{queryId}/refetch`，`POST /search/query`，`PATCH /search/{queryId}/watch`，`DELETE /search/{queryId}`，`GET /summary`，`GET /summary/ui`，`GET /summary/{stateId}`，`GET /summary/{stateId}/raw`，`POST /summary`，`DELETE /summary/{stateId}`，`GET /health`；内部隐藏：`POST /llm`、`POST /vlm`、`GET /states/{stateId}`、`GET /states/raw/{stateId}` |
| video-search-and-summarization (search-ms) | `sample-applications/video-search-and-summarization/search-ms/` | 向量检索服务（FastAPI） | 服务根路径 | `POST /query`，`GET /watcher-last-updated`，`GET /health`，`GET /initial-upload-status` |
| plcopen-benchmark | `sample-applications/plcopen-benchmark/` | PLCopen 基准测试（C++） | N/A | 未发现 HTTP API |
| plcopen-databus | `sample-applications/plcopen-databus/` | PLCopen 数据总线（C++） | N/A | 未发现 HTTP API |

> 备注：如需导出为 OpenAPI 或进一步拆分字段级请求/响应说明，请告知前端对接格式需求。
