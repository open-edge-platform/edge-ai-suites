# Smart Classroom Session API — 用户集成指南

本文档面向**集成 Smart Classroom 的客户/合作伙伴**,说明如何通过 3 个接口,让后端帮你完成一整堂课的自动处理(转写、摘要、思维导图、视频分析、分段、报告)。

你只需要:
1. 调用 1 个接口提交任务;
2. 轮询 1 个接口查进度;
3. 处理完成后,到返回的目录里取结果。

后端负责执行顺序、依赖关系、音频/视频并行处理——你**不需要**理解内部流程,也不用自己串联各个功能。

---

## 使用流程(3 步)

```
第 1 步  提交任务  →  拿到 session_id
第 2 步  轮询进度  →  直到 "completed" 或 "failed"
第 3 步  取产物     →  到 output_dir 目录读文件
```

---

## 接口一览

| 接口 | 作用 |
|---|---|
| `POST /sessions/process` | 提交一个处理任务(自动创建 session,后台异步执行) |
| `GET /sessions/{session_id}/status` | 查询任务状态和进度 |
| `GET /sessions` | (可选)列出所有任务记录 |

---

## 1. 提交任务

**`POST /sessions/process`**

### 请求体

| 字段 | 必填 | 说明 |
|---|---|---|
| `audio_path` | 否 | 音频文件在本机的路径。**只有当你要做音频处理时才需要**。 |
| `video_sources` | 否 | 视频文件在本机的路径(可多个)。**只有当你要做视频分析时才需要**。 |
| `stages` | **是** | 本次要处理哪些环节。**必须至少选一个。** |

`video_sources` 支持:`front`(前摄像头)、`back`(后摄像头)、`content`(板书/大屏),可按需提供。

`stages` 可选值:

| 值 | 含义 | 是否需要大模型 |
|---|---|---|
| `transcribe` | 语音转写(音频 → 文字) | 否 |
| `summarize` | 课堂摘要 | 是 |
| `mindmap` | 思维导图 | 是 |
| `va` | 视频分析(姿态/课堂行为) | 否 |
| `segmentation` | 内容/主题分段 | 是 |

**说明:**
- `stages` 只声明"**要哪些环节**",执行顺序由后端决定。你不用排序。
- 没选的环节会显示为 `skipped`(跳过)。
- 想只做转写:`["transcribe"]`(纯转写,不调用大模型)。
- 想只做视频分析:`["va"]`(完全不碰音频)。
- 选了某个环节但没给对应文件(如要 `transcribe` 却没给 `audio_path`),会返回错误。

### 示例

**完整一堂课:**
```json
{
  "audio_path": "D:\\media\\class1.wav",
  "video_sources": {
    "front": "D:\\media\\front.mp4",
    "back": "D:\\media\\back.mp4"
  },
  "stages": ["transcribe", "summarize", "mindmap", "va", "segmentation"]
}
```

**只转写:**
```json
{
  "audio_path": "D:\\media\\class1.wav",
  "stages": ["transcribe"]
}
```

**只做视频分析:**
```json
{
  "video_sources": { "front": "D:\\media\\front.mp4" },
  "stages": ["va"]
}
```

### 返回(立即返回,后台继续执行)

```json
{
  "session_id": "20260807-143518-0085",
  "stages": { "transcribe": "pending", "va": "pending" },
  "output_dir": "C:\\...\\storage\\smart-classroom\\20260807-143518-0085",
  "started_at": "2026-08-07T06:35:18+00:00"
}
```

**请记下 `session_id`**,下一步用它查进度。

---

## 2. 查询任务状态

**`GET /sessions/{session_id}/status`**

把上一步拿到的 `session_id` 填进去。

### 返回

```json
{
  "session_id": "20260807-143518-0085",
  "state": "running",
  "current_stage": "va",
  "stages": {
    "transcribe": "done",
    "summarize": "done",
    "mindmap": "done",
    "va": "running",
    "segmentation": "pending"
  },
  "sources": {
    "audio": "class1.wav",
    "video": { "front": "front.mp4", "back": "back.mp4" }
  },
  "output_dir": "C:\\...\\storage\\smart-classroom\\20260807-143518-0085",
  "error": null,
  "started_at": "2026-08-07T06:35:18+00:00",
  "updated_at": "2026-08-07T06:42:39+00:00"
}
```

### 关键字段

| 字段 | 含义 |
|---|---|
| `state` | 任务整体状态:`pending`(等待)/ `running`(执行中)/ `completed`(完成)/ `failed`(失败)。**`completed` = 处理完成,可以取结果了。** |
| `current_stage` | 当前执行到哪个环节。 |
| `stages` | 每个环节的状态:`pending`(等待)/ `running`(执行中)/ `done`(完成)/ `skipped`(未选)/ `failed`(失败)。 |
| `sources` | 本次处理的源文件名。 |
| `output_dir` | **产物目录的完整路径**,完成后到这里读文件。 |
| `error` | 失败原因(仅 `state=failed` 时有值)。 |
| `started_at` / `updated_at` | 开始时间 / 最后更新时间,可用于计算已运行时长。 |

### 怎么判断成功

轮询本接口,直到:
- `state == "completed"` → 成功,去 `output_dir` 取产物。
- `state == "failed"` → 失败,看 `error` 字段的原因。

---

## 3. 列出所有任务(可选)

**`GET /sessions`**

返回所有任务记录,方便管理/盘点:

```json
{
    "total": 2,
    "sessions": [
        {
            "session_id": "20260807-140806-8df1",
            "state": "completed",
            "current_stage": "segmentation",
            "stages": {
                "transcribe": "done",
                "summarize": "done",
                "mindmap": "done",
                "va": "done",
                "segmentation": "done"
            },
            "sources": {
                "audio": "input_part_5min.wav",
                "video": {
                    "front": "qian5.mp4",
                    "back": "hou5.mp4"
                }
            },
            "started_at": "2026-08-07T06:08:06+00:00",
            "updated_at": "2026-08-07T06:16:40+00:00"
        },
        {
            "session_id": "20260807-142413-93cd",
            "state": "completed",
            "current_stage": "segmentation",
            "stages": {
                "transcribe": "done",
                "summarize": "done",
                "mindmap": "done",
                "va": "done",
                "segmentation": "done"
            },
            "sources": {
                "audio": "input_part_5min.wav",
                "video": {
                    "front": "qian5.mp4",
                    "back": "hou5.mp4"
                }
            },
            "started_at": "2026-08-07T06:24:13+00:00",
            "updated_at": "2026-08-07T06:31:44+00:00"
        }
    ]
}
```

---

## 产物在哪里

处理完成后,到 `output_dir` 目录读文件。目录按三类组织:

| 目录 | 放什么 | 例子 |
|---|---|---|
| `result/` | 大模型生成的最终成果 | `summary.md`、`mindmap.mmd`、`topics.json` |
| `raw/` | 中间产物与原始数据 | `transcription.txt`、录像 mp4、视频分析统计 |
| `logs/` | 监控/运行日志 | 性能指标、运行日志 |

直接按文件名读取对应产物即可。

---

## 注意事项

- **文件必须在本机**:`audio_path` / `video_sources` 填的是运行 Smart Classroom 的那台机器上的**本地路径**。本接口不支持 RTSP 流。
- **轮询节奏**:没有回调,请间隔数秒轮询 `status`(建议 5~10 秒一次)直到完成。
- **失败即停**:某个环节失败,整个任务会标记为 `failed` 并停止,`error` 会给出原因。
- **一次一个任务**:当前版本一次只处理一个 session,不支持并发提交多个。

---

## 完整调用示例

```bash
# 1. 提交任务
curl -X POST http://<host>:8000/sessions/process \
  -H "Content-Type: application/json" \
  -d '{
    "audio_path": "D:\\media\\class1.wav",
    "video_sources": { "front": "D:\\media\\front.mp4" },
    "stages": ["transcribe", "va"]
  }'

# 2. 查进度(把 session_id 填进去)
curl http://<host>:8000/sessions/20260807-143518-0085/status

# 3. 查看所有任务
curl http://<host>:8000/sessions
```
