# Smart Classroom Session API — 用户集成指南

本文档面向**集成 Smart Classroom 的客户/合作伙伴**,说明如何通过 3 个接口,让后端帮你完成一整堂课的自动处理(转写、摘要、思维导图、视频分析、分段、报告)。

你只需要:
1. 调用 1 个接口提交任务;
2. 轮询 1 个接口查进度;
3. 处理完成后,到返回的目录里取结果。

后端负责执行顺序、依赖关系、音频/视频并行处理——你**不需要**理解内部流程,也不用自己串联各个功能。

---

## 第一节:Session 相关 API

### 使用流程(3 步)

```
第 1 步  提交任务  →  拿到 session_id
第 2 步  轮询进度  →  直到 "completed" 或 "failed"
第 3 步  取产物     →  到 output_dir 目录读文件
```

---

### 接口一览

| 接口 | 作用 |
|---|---|
| `POST /sessions/process` | 提交一个处理任务(自动创建 session,后台异步执行) |
| `GET /sessions/{session_id}/status` | 查询任务状态和进度 |
| `GET /sessions` | (可选)列出所有任务记录 |

---

### 1. 提交任务

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

### 2. 查询任务状态

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

### 3. 列出所有任务(可选)

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

### 产物在哪里

处理完成后,到 `output_dir` 目录读文件。目录按三类组织:

| 目录 | 放什么 | 例子 |
|---|---|---|
| `result/` | 大模型生成的最终成果 | `summary.md`、`mindmap.mmd`、`topics.json` |
| `raw/` | 中间产物与原始数据 | `transcription.txt`、录像 mp4、视频分析统计 |
| `logs/` | 监控/运行日志 | 性能指标、运行日志 |

直接按文件名读取对应产物即可。

---

### 注意事项

- **文件必须在本机**:`audio_path` / `video_sources` 填的是运行 Smart Classroom 的那台机器上的**本地路径**。本接口不支持 RTSP 流。
- **轮询节奏**:没有回调,请间隔数秒轮询 `status`(建议 5~10 秒一次)直到完成。
- **失败即停**:某个环节失败,整个任务会标记为 `failed` 并停止,`error` 会给出原因。
- **一次一个任务**:当前版本一次只处理一个 session,不支持并发提交多个。

---

### 完整调用示例

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

---

## 第二节:Legacy 音频接口(`/upload-audio` / `/transcribe`)

> ⚠️ **建议优先使用 `/sessions/process`**
>
> 这两个接口是早期版本暴露的**独立音频接口**,目前仍在服务、可正常使用,但由于已经对外,暂时无法移除。
> **后续新集成请统一走本文档主流程的 `POST /sessions/process` + `GET /sessions/{session_id}/status`**,本附录仅用于兼容已有调用方。
>
> 与 session 接口的区别:
> - `/upload-audio` + `/transcribe` 需要先传文件、再逐个 chunk 流式拿转写,还要自己管理会话与并发锁(429)。
> - `/sessions/process` 一次提交 `audio_path` + `stages`,后端自动完成转写等全流程,返回 `output_dir` 后直接读结果文件。

### 1. `POST /upload-audio`

**用途**:上传音频文件,为后续 `/transcribe` 做准备。

**请求:**

| 类型 | 参数 | 必填 | 格式 | 说明 |
|---|---|---|---|---|
| Body | `file` | 是 | multipart/form-data | 音频文件(字段名**固定为 `file`**,不能改名) |

**约束:**
- 扩展名必须是 `.wav` / `.mp3` / `.m4a`
- 单文件 ≤ 300 MB
- 若上一次会话仍在处理(`audio_pipeline_lock` 未释放),返回 **429** `"Session Active, Try Later"`

**返回:**
```json
{
  "filename": "input_part_5min.wav",
  "message": "File uploaded successfully",
  "path": "storage/smart-classroom/audio/input_part_5min.wav"
}
```

> **注意**:`path` 是**相对路径**,基准是服务端进程的工作目录。下一步 `/transcribe` 需要把返回的 `path` 原样填进 `audio_filename`。

**示例:**
```bash
curl -X POST http://<host>:8000/upload-audio \
  -F "file=@input_part_5min.wav"
```

---

### 2. `POST /transcribe`

**用途**:对已上传的音频做语音转写(ASR),流式按 chunk 返回文本和时间戳。

**请求:**

| 类型 | 参数 | 必填 | 格式 | 说明 |
|---|---|---|---|---|
| Header | `x-session-id` | 否 | string | 会话 ID(可选) |
| Body | `audio_filename` | 是 | string | `/upload-audio` 返回的 `path`(**完整路径**,不是裸文件名) |
| Body | `source_type` | 否 | string | `audio_file`(默认)或 `microphone` |

**请求体:**
```json
{
  "audio_filename": "storage/smart-classroom/audio/input_part_5min.wav",
  "source_type": "audio_file"
}
```

**返回(流式,JSON 行,每行一个 chunk):**

```json
{
  "chunk_path": "chunks/chunk_0_7f2288.wav",
  "start_time": 0.0,
  "end_time": 15.0,
  "chunk_index": 0,
  "text": "好，\n小朋友们，\n上课前呢田老师想先跟小朋友们讲解一下我们今天这节课的课堂评价。\n",
  "segments": [
    { "speaker": "教师", "text": "好，", "start": 7.54, "end": 7.78 }
  ]
}
```

结束事件:
```json
{
  "event": "final",
  "teacher_speaker": "教师",
  "speaker_text_stats": { "教师": 5234 }
}
```

**注意:**
- 响应头会带 `x-session-id`,可用于后续查询。
- 每次转写结束后需等锁释放才能发起下一次(否则 **429**)。
- `audio_filename` 用正斜杠(`storage/smart-classroom/audio/...`)也可以,Windows 下无需特意转义反斜杠。

**示例:**
```bash
curl -X POST http://<host>:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_filename": "storage/smart-classroom/audio/input_part_5min.wav", "source_type": "audio_file"}'
```

---

## 第三节:VLM / LLM 接口(独立服务)

外部客户在集成 Smart Classroom 时,也可以**直接调用下面这个大模型接口**来使用 VLM / LLM 能力,不需要走完整的课堂处理流程。

### 接口

```
POST http://<host>:8000/v1/chat/completions
```

**OpenAI 兼容格式**——客户可以用标准的 OpenAI 客户端直接调用。

- 纯文本请求(当 **LLM** 用)
- 图文请求(当 **VLM** 用,消息里带图片路径/URL)
- 支持流式 / 非流式

### 支持的模型

服务端当前支持以下模型(OpenVINO 量化版本):

| 模型 | 支持的量化 |
|---|---|
| `Qwen/Qwen3-VL-8B-Instruct` | int4、int8 |
| `Qwen/Qwen3.5-9B` | int4、int8 |
| `Qwen/Qwen3.6-35B-A3B` | int4、int8 |

说明:

- **当前默认**为 `Qwen/Qwen3-VL-8B-Instruct`(config 里 `vlm_name`),多模态。
- `Qwen/Qwen3.5-9B` 和 `Qwen/Qwen3.6-35B-A3B` 仅在 `device: GPU` + `weight_format: int8` 下验证过。
- **切换模型**需改服务端 `config.yaml` 的 `text_gen.vlm_name`(以及 `weight_format`、`device`),重启服务生效。
- 接口的 `model` 参数会被忽略——**以服务端配置的模型为准**,客户传入 `model` 名不会切换模型。
- 具体可用模型和量化由服务端部署决定;若需在部署上新增模型,请与服务提供方确认。

### 用 OpenAI 客户端调用(推荐)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",   # 指向本服务的 VLM 端点
    api_key="unused",                        # 本服务无鉴权,任意值
)

# 纯文本(当作 LLM)
resp = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",       # 可选,省略则用服务端配置的模型
    messages=[
        {"role": "system", "content": "你是课堂助手,回答简洁。"},
        {"role": "user", "content": "总结这段课堂转写的要点"},
    ],
    temperature=0.3,
)
print(resp.choices[0].message.content)

# 图文(当作 VLM,image_url 可填本机图片路径或 URL)
resp = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "这张板书上写了什么?"},
            {"type": "image_url", "image_url": {"url": "C:/path/to/board.jpg"}},
        ],
    }],
)
```

### 用 curl 调用

```bash
# 纯文本
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"你好,介绍一下你自己"}]}'

# 图文
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages":[{
      "role":"user",
      "content":[
        {"type":"text","text":"这张图里有什么?"},
        {"type":"image_url","image_url":{"url":"C:\\path\\to\\board.jpg"}}
      ]
    }]
  }'
```

### 支持的能力

| 能力 | 说明 |
|---|---|
| 纯文本 / 图文 | 只有 prompt 时按 LLM 处理;带图片时按 VLM 处理 |
| 流式 | 请求加 `"stream": true`,响应为 SSE 流(`data: {...}` 直到 `data: [DONE]`) |
| `model` | 可选,省略时用服务端 config 的模型;传了也会被忽略(以服务端为准) |
| `temperature` / `max_completion_tokens` / `enable_thinking` | 均可设置 |

### 注意事项

- **无鉴权**:该接口未做访问控制,仅适合本机 / 内网使用;暴露到公网需自行加保护。
- **单轮**:只取最后一个 user 消息作为输入。需要多轮对话时,客户需自行把历史拼接进最后一个 user 消息。
- **依赖模型已加载**:调用前需确保服务已启动且大模型已加载(text_gen 配置为启用)。
