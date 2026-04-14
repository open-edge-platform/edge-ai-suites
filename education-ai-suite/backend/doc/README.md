# edu-ai-backend
## User Guide
## API Compatibility Map
See `api-map.md` for the full sample-applications API table.
### Start Redis
```
C:\Program Files\Redis
```

### Start PostgreSQL
```
C:\Program Files\PostgreSQL\16
```

### Install dependencies
```
conda activate edu-ai
```

### Start Dummy_app
```
python mock_services/dummy_ai_provider.py
```

### Start Main
```
python main.py
```

### Start Worker
```
python worker_run.py
```

### For test
#### Postman
```
POST http://127.0.0.1:8000/api/tasks/video-summary
{
  "video_url": "https://example.com/video.mp4",
  "sync": true
}
```

## Note
### Ingrediences
FastAPI
Redis Streams

### Process Manager
A: NSSM (The Non-Sucking Service Manager)
B: PM2

### Data persistance
PostgreSQL

### API Test
Postman

### Support
同步返回：
搜索/Embedding（通常几百毫秒，FastAPI 收到请求 -> 丢进 Redis -> 等待结果 -> 返回给前端）。
异步通知(Webhook/WebSocket)：
视频摘要（可能需要几分钟，API 直接返回 task_id，Worker 完成后通过 WebSocket 推送给前端，或者前端定时轮询）。

## Archecture
### route and loadcontrol
VRAM？

Redis Streamer
- 为每种不同的任务创建不同类型的stream，例如 stream:embedding, stream:summary
- worker隔离，启动多个worker进程，例如worker_cpu, worker_gpu, worker_npu
Resource Locking
- 利用 Redis 的分布式锁（Redlock）。Worker 在加载大模型前，先去 Redis 抢占一个“显存锁”。抢不到说明显存满了，Worker 进入等待，从而避免 OOM。

#### 关于redis分布式锁与redlock算法
分布式锁的核心作用是确保同一个时间只有一个worker占用显存来加载或者运行某个重型模型

### 长耗时任务的异步闭环
长耗时任务，前端不能一直挂起 HTTP 连接。需要实现 “提交-轮询/推送” 模式
#### 提交阶段
FastAPI接收请求，在PostgreSQL中创建一个任务记录，状态为PENDING
将任务ID和参数推入Redis Streams
立即向前端返回 {"task_id": "xxx", "status": "accepted"}

#### 处理阶段
worker领取任务，更新数据库状态为PROCESSING
worker调用对应的微服务的API

#### 交付阶段
执行完成后，worker将结果写入PostgreSQL (文本，metadata)
更新状态为SUCCESS
主动推送： FastAPI通过websocket通知前端

### 任务管理
状态(Status)：

QUEUED(入队)：任务已创建，在redis中排队
PROCESSING(处理中)：worker已经领走任务，已经发给对应API
COMPLETED(已完成)：各个微服务API给出成功结果
FAILED(失败)：微服务API给出失败结果
RETRYING(重试中)：处理失败，尝试重新执行

### 多用户？
暂时先在backend中预留`user_id`字段

### Stucture
```
/my_orchestrator
├── /api            # FastAPI 路由（生产者）
├── /core           # 核心逻辑（任务状态机、微服务客户端）
├── /workers        # 任务监听器（消费者）
├── config.py       # 读取 .env 环境变量
├── main.py         # FastAPI 启动入口
└── worker_run.py   # Worker 启动入口
```

### others
#### install conda (miniforge) and setup env
```powershell
conda create -n edu-ai python=3.12
conda activate edu-ai
```
```powershell
# .condarc
channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
  - https://mirrors.ustc.edu.cn/anaconda/cloud/conda-forge/
  - conda-forge
mirrored_channels:
  conda-forge:
    - https://conda.anaconda.org/conda-forge
    - https://prefix.dev/conda-forge
ssl_verify: false
proxy_servers:
  http: http://proxy-dmz.intel.com:911
  https: http://proxy-dmz.intel.com:912
```

```powershell
conda install -c conda-forge psycopg2 redis-py
pip install fastapi uvicorn httpx pydantic-settings
```
python (3.12.x)
C:\Users\user\miniforge3\python.exe

```powershell
# backup env
conda env export > environment.yml
# restore env
conda env create -f environment.yml
```
## other dependiencies

pip install python-multipart

#### install Redis
https://github.com/tporadowski/redis/releases
#### install PostgreSQL
16.11.3
https://www.postgresql.org/download/windows/
passwd: edu-ai
port: 5432
#### install postman


### how to run
#### Terminal A
& "C:\Users\user\miniforge3\envs\edu-ai\python.exe" .\main.py
#### Terminal B
& "C:\Users\user\miniforge3\envs\edu-ai\python.exe" .\worker_run.py
#### Terminal C
& "C:\Users\user\miniforge3\envs\edu-ai\python.exe" .\mock_services\dummy_ai_provider.py
#### webhook.site
https://webhook.site/
unique URL: e.g. https://webhook.site/28865adb-376c-4a0a-ac59-5204a60f9fe3
#### postman
Method: POST
URL: http://127.0.0.1:8000/api/tasks/video-summary
Body Type: raw (选择 JSON)
```json
{
    "video_url": "C:/videos/videos/classroom_test.mp4",
    "sync": false,
    "callback_url": "https://webhook.site/28865adb-376c-4a0a-ac59-5204a60f9fe3"
}
```

#### 这个example执行的动作

1. Postman 将任务交给了 FastAPI (8000)。
2. FastAPI 把任务存入 PostgreSQL，并将任务 ID 扔进 Redis 队列，随后立即向你返回了 QUEUED。
3. Worker 从 Redis 中“抢”到了这个 ID，通过 Processor 模块跨进程请求了 Mock AI 服务 (8001)。
4. Mock AI 计算了 3 秒，把结果给回了 Worker。
5. Worker 把结果存回数据库，并根据你提供的 callback_url，跨越互联网把结果推到了 Webhook.site 的服务器上。
