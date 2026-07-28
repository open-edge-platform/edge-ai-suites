## Plan: Release-Safe Clean-Server Guide

将主入门流程重构为“无 use case、无监控器的纯净 MCP 服务”，把可选的三用例演示完整迁移到独立文档。发布包不再携带 demo MP4；四路 RTSP 流默认启用并通过环境变量接收本地视频路径，缺失或无效的视频会警告后自动跳过。

**Steps**
1. 更新 `demo/videos/streams.yaml`
   - 四个流全部默认设为 `enabled: true`。
   - 每个 `file` 改为独立环境变量占位符。
   - 保留现有 RTSP 地址和循环行为，补充用户导出视频绝对路径的说明。

2. 修改 `demo/videos/start-streams.sh`
   - 在独立 YAML 解析逻辑中实现 `${VAR}` 环境变量展开，语义对齐 `packages/mcp-server/src/config.ts`。
   - 已启用流的变量未设置、展开为空或文件不存在时，输出明确 warning，自动将该流视为 `enabled: false` 并继续启动其余流。
   - 保留显式 `enabled: false` 的完全跳过行为，允许用户手动停用任意流。
   - 更新 `demo/scripts/start-demo.sh`，使它只将实际可启动流对应的 monitor 传给 MCP server；避免视频被跳过后，`monitors.demo.yaml` 中对应的监控器仍被注册并尝试连接不存在的 RTSP 地址。

3. 解除发布与测试对视频的依赖
   - 保留用户本地的 `demo/videos/` MP4；该目录已被 Git ignore，视频不会随 release 发布。
   - 将 `videostream-analytics/tests/conftest.py` 中对 `child_safety_demo.mp4` 的依赖替换为测试时生成的、包含确定性运动画面的临时视频。
   - 更新 VSA 测试/评测脚本、工具说明中硬编码的视频名，使其改为接收用户传入的视频目录或路径，并在缺失时提前失败。

4. 重写 `docs/user-guide/get-started.md`
   - 以纯净服务为主线：前置要求、克隆、启动依赖服务、健康检查、启动 `scripts/mcp-server/start.sh`、验证空服务、接入 MCP 客户端、注册新的 use case。
   - 保留并重排 rebase 后新增的 `## Register a new use case`：将其置于 clean server 启动并连接 agent 之后，改为不引用三个 demo 的简短入口，并链接 `get-started/register-new-use-case.md`；不要在主指南重复该页面的 Q1/Q2、两步注册和 schema 细节。
   - 移除现有 `## Run a clean, use-case-free server` 中重复的 use case / camera 操作清单；注册指南已说明提供 stream URL 时会自动调用 `smartbuilding_monitor_ctl register_source`，未提供时可稍后绑定摄像头。
   - 移除全部预配置 demo、RTSP、示例摄像头和演示问答内容。
   - 在合适位置链接可选 demo 指南。

5. 对齐注册新 use case 指南
   - 更新 `docs/user-guide/get-started/register-new-use-case.md`，使其从“纯净服务器已启动且 agent host 已连接”的视角介绍流程，移除“三个 demo monitors”作为前提或开场。
   - 保留现有完整注册契约：导入 skill、Q1/Q2 确认、Final Schema、`register_task` 后 `register` 的两步流程、`persist=true`，以及有 `source_url` 时自动绑定 monitor。
   - 检查它的前置条件链接、`Run a clean` 交叉引用和 `docs/user-guide/index.md` 链接，确保重排后的标题锚点仍正确。

6. 编写 `docs/user-guide/get-started/ready-to-run-demo.md`
   - 在 prerequisites 中说明 demo 支持四路视频分析，发布默认全部 `enabled: true`，但视频不随发布包分发。
   - 列出四路视频各自的一句用途说明；用户可自行准备任意子集的兼容 MP4 并导出对应环境变量，未准备或无法读取视频的流会显示 warning 后自动跳过。
   - 给出启动 RTSP、验证流、启动 demo server、验证已启用监控器、连接 agent、停止服务的完整步骤。
   - 收纳全部 OpenClaw demo 内容：运行 demo 专用 `packages/framework-adapter-sdk/examples/openclaw/scripts/install.sh`、可选的开发模型配置、预置 personas、`cam_child` / `cam_elder_bedroom` 路由、演示 cron 任务和预期 dashboard 行为。

7. 对齐其余文档和启动提示
   - 更新 `demo/README.md`、`use-cases/README.md`、根 `README.md` 以及 `config.yaml.example` 中相关注释。
   - 修改 `demo/scripts/start-demo.sh` 的“bundled clips”表述，使其引导到流配置和缺失视频的错误提示。
   - 清理硬编码视频名及“仓库随带视频”的陈述，确保新 demo 指南可被发现。
   - 将 `packages/framework-adapter-sdk/examples/openclaw/README.md` 改为 clean-server 通用 adapter 参考：只保留架构、通用先决条件、插件构建/安装、任意 `monitor_id → OpenClaw session` 路由配置、字段说明与订阅数据流；删除三用例 monitor、预置 agents/personas、`scripts/install.sh`、`fire_models.sh`、demo cron 与 dashboard 说明，转而链接 `ready-to-run-demo.md`。
   - 从 `docs/user-guide/get-started.md` 的 OpenClaw 段落移出“full demo / multi-agent / ready-to-use adapter plugin”描述；保留 clean MCP server 的直接接入和 reactive 用法，并将通用 proactive adapter 指向 adapter README，将 ready-to-run demo 指向 demo guide。

8. 验证
   - 运行 shell 语法检查。
   - 覆盖显式关闭、变量缺失后自动跳过、有效视频路径及不存在文件后自动跳过四种流配置情况。
   - 运行 VSA 非集成 pytest，确认临时测试视频可覆盖运动/Pipeline 测试。
   - 运行 MCP server 的 `python run_all.py` 与 `npm run build`。
   - 搜索发布路径中旧视频文件名的硬编码引用，并确认本地 MP4 仍由 Git ignore 排除在发布内容外。
   - 检查文档边界：主 `get-started.md` 不包含 demo agents、cron 或预置 monitor；adapter README 不包含 Fridge/Child/Elder 的 demo 配置；这些内容仅出现在 `ready-to-run-demo.md`。
   - 从干净服务路径人工走读：启动空 MCP server → 连接 agent / 导入 skill → 通过 `Register a New Use Case` 注册用例；验证提供 `source_url` 时 camera 绑定由注册流程完成。

**关键决定**
- 四路流发布默认全部启用；未设置、为空或无效的视频环境变量会让启动脚本警告并自动跳过对应流。
- demo 功能保留；本地视频由用户自行准备，且已由 Git ignore 排除在发布内容外。
- 范围包括所有会假定视频已随包存在的组件文档、脚本与测试；不扩展为远程下载或 URL 视频支持。
- `config.yaml.example` 的空 `use_case_dict` 和无监控器启动模式继续作为正式默认路径。
