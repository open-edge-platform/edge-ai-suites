# Unit Tests

本目录存放新代码的 pytest 单元测试。运行:`python -m pytest tests/`

共 **27** 个用例。

## test_session_paths.py — SessionPaths 工具类

验证 `utils/session_paths.py` 的路径拼接逻辑(config 的 project location/name 派生,跨平台用 `pathlib.Path`)。

| 测试 | 验证内容 |
| :--- | :--- |
| test_base_dir | `base_dir()` = `<location>/<name>`(项目根) |
| test_session_dir | `session_dir(sid)` = `<location>/<name>/<sid>` |
| test_va_dir | `va_dir(sid)` = session 目录下加 `va` |
| test_transcript_path | `transcript_path(sid)` 指向 `transcription.txt` |
| test_segmentation_transcript_path | `segmentation_transcript_path(sid)` 指向 `content_segmentation_transcription.txt` |
| test_summary_path | `summary_path(sid)` 指向 `summary.md` |
| test_mindmap_path | `mindmap_path(sid)` 指向 `mindmap.mmd` |
| test_topics_path | `topics_path(sid)` 指向 `topics.json` |
| test_returns_path_objects | 返回值类型为 `pathlib.Path` |

## test_session_service.py — session 业务层

验证 `services/session_service.py` 的业务逻辑(校验、编排、查询、删除),通过 mock `SessionStore` / `orchestrator` 隔离依赖。

| 测试 | 验证内容 |
| :--- | :--- |
| test_create_process_rejects_empty_stages | stages 为空 → 抛 `SessionValidationError` |
| test_create_process_rejects_unknown_stage | 非法 stage 名 → 抛 `SessionValidationError` |
| test_create_process_rejects_missing_audio_for_transcribe | transcribe 缺 `audio_path` → 抛 `SessionValidationError` |
| test_create_process_rejects_nonexistent_audio | `audio_path` 文件不存在 → 抛 `SessionValidationError` |
| test_create_process_calls_orchestrator | 校验通过后确实调用 `orchestrator.start_process` |
| test_get_status_not_found | session 不存在 → 抛 `SessionNotFound` |
| test_get_status_returns_state | 返回状态 dict,含 `output_dir` |
| test_list_sessions | 列表返回 + `total` 计数正确 |
| test_delete_not_found | 删除不存在的 session → 抛 `SessionNotFound` |
| test_delete_rejects_running | 删除 running 中的 session → 抛 `SessionRunning` |
| test_delete_removes_dir | 删除记录并清空磁盘目录 |

## test_va_completion.py — VA 完成检测

验证 `utils/va_completion.py` 的 `wait_for_va_completion`,用 `FakeService` 模拟 VA 服务的完成信号(回调 / final_status / 进程存活)。

| 测试 | 验证内容 |
| :--- | :--- |
| test_done_event_returns_immediately | 回调(done)已 set → 立即判定完成 |
| test_all_final_status_eos_returns_true | 所有 pipeline 终态为 eos → 完成 |
| test_any_final_status_failed_returns_true | 任一 pipeline 终态为 failed → 完成(失败也算结束) |
| test_all_processes_down_fallback_returns_true | 无终态记录但进程全部退出 → 通过兜底判定完成 |
| test_running_until_timeout_returns_false | pipeline 一直运行 → 超时返回 False |
| test_final_status_refreshed_into_caller_dict | 完成后把 `pipeline_final_status` 刷进调用方 dict |
| test_brief_dip_does_not_complete_prematurely | 进程短暂掉线又恢复 → 不误判完成 |
