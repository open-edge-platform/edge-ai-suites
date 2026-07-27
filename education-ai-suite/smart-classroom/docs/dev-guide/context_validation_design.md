<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Context Validation 功能组件设计解析

## 1. 文档目的

本文从代码实现角度解析 `components/llm/context_validation/`。该组件用于回答：

> 对给定模型、OpenVINO 权重格式、推理设备和目标硬件，能够稳定完成 prefill 并继续 decode 的最大上下文长度是多少？该长度是否达到目标值？

这里的 `context validation` 是**硬件容量验证**，不是长文本理解质量评测。一次通过只证明当前机器能够装载模型、处理指定 token 数的提示词，并产生少量有效输出；它不证明模型能够准确回忆长上下文前部的信息，也不评价摘要质量。

组件是独立诊断工具，不在生产推理链路中运行：

- 使用自己的 `components/llm/context_validation/config.yaml`；
- 不读取或修改主应用的 `smart-classroom/config.yaml`；
- 每次试验在独立子进程中加载模型；
- 将逐次原始结果与模型级汇总写入独立输出目录。

现有 `validate_long_context.md` 更侧重使用和环境准备，本文重点说明内部设计、控制流、数据流、判定逻辑与实现边界。

## 2. 目录与职责

```text
components/llm/context_validation/
├── config.yaml
├── context_builder.py
├── trial_runner.py
├── validate_long_context.py
├── setup_env.ps1
└── run_validate_long_context.ps1
```

| 文件 | 核心职责 |
|---|---|
| `validate_long_context.py` | CLI 编排器；加载配置、扫描模型与上下文阶梯、管理子进程、采样内存、执行通过策略、写报告。 |
| `trial_runner.py` | 单次试验执行器；在子进程中加载 tokenizer 和 OpenVINO pipeline，构造提示词、执行生成并验证输出。 |
| `context_builder.py` | 合成长课堂转录文本，并根据目标 token 数扣除聊天模板开销，使最终 prompt 尽量命中目标长度。 |
| `config.yaml` | 组件私有配置；定义候选模型、目标长度、扫描阶梯、SLA、超时和输出目录。 |
| `run_validate_long_context.ps1` | 一键入口；定位并激活后端虚拟环境，将工作目录切换到 `smart-classroom/` 后启动 Python 模块。 |
| `setup_env.ps1` | 创建或复用仓库后端虚拟环境，并安装 `requirements.txt`。 |

三个 Python 文件形成明确的职责边界：

1. `context_builder.py` 只处理“输入规模”；
2. `trial_runner.py` 只处理“一次真实推理”；
3. `validate_long_context.py` 处理“多次试验的生命周期、策略和报告”。

这种拆分使 prompt 构造和策略判断可在没有 OpenVINO、GPU 或真实模型的条件下单元测试。

## 3. 总体架构

```mermaid
flowchart TB
    CLI[PowerShell / Python CLI] --> ORCH[validate_long_context.py<br/>父进程编排器]
    CFG[独立 config.yaml] --> ORCH
    ORCH --> CHECK[环境与 IR 检查]
    CHECK --> SWEEP[按模型、按 token 阶梯扫描]
    SWEEP --> SAMPLE[MemorySampler<br/>父进程采样线程]
    SWEEP --> CHILD[trial_runner.run_trial<br/>独立 spawn 子进程]
    CHILD --> TOK[HuggingFace Tokenizer]
    CHILD --> BUILD[context_builder.py<br/>构造目标长度 prompt]
    CHILD --> OV[OpenVINO GenAI<br/>LLMPipeline / VLMPipeline]
    CHILD -- loaded / done --> SWEEP
    SAMPLE --> POLICY[容量与资源策略]
    SWEEP --> POLICY
    POLICY --> CSV[trials.csv]
    POLICY --> SUMMARY[summary.json / summary.md]
```

设计的关键不是简单调用一次 `generate()`，而是把不稳定的硬件试验包装成可恢复、可度量的扫描过程：

- 子进程承受 OOM、驱动异常和挂起风险；
- 父进程在子进程之外保留超时控制和峰值数据；
- 阶梯扫描定位粗粒度上限；
- 可选二分细化缩小最后成功与首次失败之间的区间；
- 原始数据与汇总数据分开保存，便于复核。

## 4. 启动与配置解析

### 4.1 PowerShell 启动链

推荐入口是 `run_validate_long_context.ps1`：

```text
run_validate_long_context.ps1
  ├─ 根据脚本路径定位 smart-classroom/
  ├─ 定位同级虚拟环境 ../smartclassroom/Scripts/python.exe
  ├─ 虚拟环境不存在时调用 setup_env.ps1
  ├─ 激活虚拟环境
  ├─ Set-Location smart-classroom/
  └─ python -m components.llm.context_validation.validate_long_context <args>
```

切换工作目录很重要，因为默认 `models_base_path` 和 `output_dir` 都是相对 `smart-classroom/` 的路径。

### 4.2 CLI 与配置合并

`main()` 首先解析参数。除 `trial_timeout_sec` 外，大部分试验参数都可通过 CLI 覆盖。`_load_settings()` 用以下优先级生成普通字典：

```text
显式 CLI 参数 > 组件私有 config.yaml > 代码中的兼容默认值
```

其中 `probe_tokens`、`max_generate_time_sec`、`gpu_memory_pressure_pct` 使用 `getattr(..., default)` 保留旧配置兼容性；候选模型、目标 token、阶梯和超时要求配置中存在。

`context_steps_tokens` 会排序，但实现不会去重，也不主动校验空列表、负值或目标值是否包含在阶梯中。因此配置应满足：

- 至少有一个正整数阶梯；
- 阶梯覆盖目标值及其上方的一个或多个点；
- `trial_timeout_sec` 大于 `max_generate_time_sec`，以便慢试验有机会返回诊断信息；
- 目标模型、设备和权重格式与计划部署环境一致。

### 4.3 环境预检

真实运行时，`_preflight_environment_check()` 使用 `importlib.util.find_spec()` 检查 `openvino_genai` 和 `transformers`。缺失时直接给出虚拟环境和启动脚本提示，避免每个扫描点重复失败。

`--dry-run` 跳过此检查。`trial_runner.py` 也将 OpenVINO 和 Transformers 放在函数内延迟导入，因此仅导入编排模块或运行 dry-run 不要求安装完整推理栈。

## 5. 模型发现与 Pipeline 选择

### 5.1 模型目录约定

`_model_ir_dir()` 按生产模型工具的路径约定构造目录：

```text
<models_base_path>/<provider>/<model_name.replace('/', '_')>_<weight_format>
```

例如：

```text
models/openvino/Qwen_Qwen3.5-9B_int8
```

### 5.2 IR 就绪检查

`_ir_ready()` 递归扫描 XML 文件，并要求同时存在：

- 一个匹配 `openvino*_model*.xml` 的模型 IR；
- `openvino_tokenizer.xml`；
- `openvino_detokenizer.xml`。

如果缺失，当前模型不进入扫描，而是返回 `status=missing_ir`，并通过 `_prep_command()` 生成可执行的 `optimum-cli export openvino` 命令。模型转换没有被隐式放入验证流程，因为大模型转换耗时、占用磁盘大，自动转换会使扫描时长和失败边界不可预测。

### 5.3 LLM/VLM 自适应

`trial_runner._load_pipeline()` 根据根目录文件选择 OpenVINO GenAI pipeline：

| IR 文件 | Pipeline |
|---|---|
| `openvino_language_model.xml` | `ov_genai.VLMPipeline` |
| `openvino_model.xml` | `ov_genai.LLMPipeline` |

两者都暴露 `generate(prompt, generation_config=...)`，因此后续试验流程不关心模型架构。

GPU 设备会附加 `GPU_ENABLE_LARGE_ALLOCATIONS=YES`，CPU 则使用空的 OpenVINO 配置。

注意：`_ir_ready()` 递归检查目录，而 `_load_pipeline()` 只检查模型目录根部。这符合当前导出布局，但若未来允许 IR 嵌套存放，两处规则需要同步调整。

## 6. Prompt 构造算法

### 6.1 为什么使用合成课堂转录

容量试验关心 token 体积，而不是固定语料的语义。组件内置多轮 `TEACHER` / `STUDENT_NN` 对话并循环扩展，原因是：

- 对话形式接近真实课堂摘要输入；
- 多样文本比重复单词更接近真实 tokenizer 合并行为；
- 不依赖外部数据文件，试验可重复；
- 最终仍带有明确任务，模型能够生成可验证的自然语言。

### 6.2 `build_text_of_token_length()`

算法过程如下：

1. 使用目标模型 tokenizer 对内置语料编码，不添加特殊 token；
2. 计算语料重复次数，确保编码后长度不小于目标值；
3. 将完整重复文本重新编码并截取前 `target_tokens` 个 token id；
4. 将 token id 解码回文本；
5. 再次编码解码后的文本，得到真实可见的 `actual_token_count`。

形式化表示为：

$$
r = \left\lfloor \frac{T}{|E(C)|} \right\rfloor + 1
$$

$$
I = E(C^r)[:T], \quad X = D(I), \quad T_{actual}=|E(X)|
$$

其中 $T$ 是目标正文 token 数，$C$ 是内置语料，$E$ 和 $D$ 分别是 tokenizer 的 encode 和 decode。

encode/decode 不一定严格互逆，因此实现返回重新编码后的实际值，而不是假设切片长度就是最终文本长度。

### 6.3 扣除聊天模板开销

目标值指完整 prefill prompt，而不仅是课堂正文。`build_context_prompt()` 先构造空正文消息，并由 `measure_template_overhead()` 计算以下固定部分的 token 开销：

- system prompt；
- user 前缀和后缀；
- role 标记及其他 chat template token；
- generation prompt。

正文预算为：

$$
T_{content}=\max(0, T_{target}-T_{overhead})
$$

随后将合成正文、固定前后缀和 system prompt 重新套入聊天模板，最终再次编码得到 `prompt_tokens`。

模板参数固定为：

```python
add_generation_prompt=True
enable_thinking=False
```

关闭 thinking 能减少模型隐式推理模式对探针输出和时延的干扰。对于 encode/decode 稳定的 tokenizer，测试要求精确命中目标；真实 tokenizer 可能因边界合并而有少量偏差，因此报告同时保存 `tokens_requested` 和 `prompt_tokens`。

## 7. 单次试验流程

### 7.1 子进程状态机

每个 `(model, context_tokens)` 组合都调用一次 `trial_runner.run_trial()`：

```mermaid
stateDiagram-v2
    [*] --> Loading
    Loading --> LoadFailed: tokenizer/pipeline 异常
    Loading --> Loaded: 模型加载成功
    Loaded --> BuildingPrompt
    BuildingPrompt --> Generating
    Generating --> ValidatingOutput: generate 返回
    BuildingPrompt --> GenerateFailed: 构造异常
    Generating --> GenerateFailed: 推理异常/OOM
    ValidatingOutput --> Done: 有效或无效输出
    LoadFailed --> Done
    GenerateFailed --> Done
    Done --> [*]
```

详细步骤：

1. 加载 HuggingFace tokenizer；
2. 根据 IR 类型加载 `LLMPipeline` 或 `VLMPipeline`；
3. 记录 `load_time_s`，发送 `loaded` 事件；
4. 构造目标长度 prompt；
5. 创建 greedy `GenerationConfig(max_new_tokens=probe_tokens, do_sample=False)`；
6. 调用 `pipe.generate()`，记录完整 prefill + decode 耗时；
7. 验证输出并计算生成 token 数；
8. 删除 pipeline、触发垃圾回收；
9. 发送 `done` 事件。

`generate_time_s` 包含长 prompt 的 prefill 和短输出的 decode，因此：

$$
tokens\_per\_second = \frac{generated\_tokens}{generate\_time\_s}
$$

只是端到端诊断指标，不是纯 decode 吞吐率。

### 7.2 Tokenizer 兼容回退

OpenVINO 导出的 tokenizer 配置可能出现两类兼容问题：

- `extra_special_tokens` 类型与 Transformers 预期不一致；
- `tokenizer_class` 名称不能被 `AutoTokenizer` 解析。

`_load_tokenizer()` 按顺序尝试四种组合：

```text
AutoTokenizer
AutoTokenizer + extra_special_tokens={}
PreTrainedTokenizerFast
PreTrainedTokenizerFast + extra_special_tokens={}
```

仅对 `ValueError` 和 `AttributeError` 回退，其他异常直接进入加载失败处理。这里的 Transformers tokenizer 只负责 prompt 定长和输出计数，真实推理由 OpenVINO IR 中的 tokenizer 完成。

### 7.3 输出有效性检查

组件不评价答案正确性，但要求 pipeline 确实产生最低限度的自然语言输出。`_validate_generated_output()` 依次拒绝：

| 条件 | 错误值 |
|---|---|
| 空字符串或纯空白 | `no_output` |
| tokenizer 编码结果为空 | `no_output_tokens` |
| 去除特殊 token 后为空 | `special_tokens_only` |
| 含 Unicode replacement character 或非法控制字符 | `invalid_characters` |
| 字母数字字符少于 3 个 | `no_semantic_output` |
| 所有字母数字字符忽略大小写后完全相同 | `repetitive_output` |

该规则能过滤 `!!!!`、`<eos>`、`aaaaaaaa` 等假成功，又避免引入任务相关的语义评分。

### 7.4 错误编码

加载或生成抛出的异常被编码为：

```text
<stage>:<classification>:<detail>
```

示例：

```text
load:oom:out of memory
generate:exception:unsupported operation
```

`_classify_error()` 用一组文本标记识别 OOM，包括 `out of memory`、`allocation failed`、`bad_alloc`、`cannot allocate` 等；其余异常归为 `exception`。父进程只读取第二段分类字段，避免异常 detail 中出现 `oom` 字样或额外冒号造成误判。

## 8. 父子进程协议与生命周期

### 8.1 为什么每次试验都使用新进程

编排器使用 `multiprocessing.get_context("spawn")`，每个扫描点创建全新 Python 子进程。主要设计收益是：

- **内存隔离**：上一次的模型对象、GPU allocation 和碎片不会污染下一次；
- **故障隔离**：OOM 或 native runtime 崩溃不会直接终止整个扫描；
- **强制回收**：试验结束或超时后，进程退出成为最终资源回收边界；
- **可观测性保留**：父进程和采样线程在子进程失败后仍能形成结果行。

代价是每个阶梯都重新加载模型，整体运行时间较长，但容量边界的可信度高于复用暖 pipeline。

### 8.2 Queue 双事件协议

子进程最多发送两个事件：

| 事件 | 时机 | 父进程用途 |
|---|---|---|
| `loaded` | tokenizer 和 pipeline 加载完成 | 立即读取一次系统内存，近似得到权重驻留快照。加载失败时不会发送。 |
| `done` | 生成成功、输出无效或捕获异常后 | 获取试验结果并结束轮询。 |

```mermaid
sequenceDiagram
    participant P as Parent Orchestrator
    participant S as MemorySampler
    participant C as Trial Child
    P->>P: baseline = read_mem()
    P->>S: start()
    P->>C: spawn run_trial()
    C->>C: load tokenizer + pipeline
    C-->>P: event=loaded
    P->>P: loaded_mem = read_mem()
    C->>C: build prompt + generate
    S->>S: sample RAM/GPU every 0.5s
    C-->>P: event=done + result
    P->>C: terminate if still alive
    P->>S: stop + join
    P->>P: merge timing, status and memory
```

### 8.3 超时与崩溃处理

父进程默认每 2 秒轮询队列，直到：

- 收到 `done`；
- 超过 `trial_timeout_sec`；
- 队列无消息且子进程已经退出。

若 deadline 到达且没有结果，状态为 `timeout`；若子进程提前退出且没有 `done`，状态为 `crashed:exitcode=N`。父进程随后终止仍存活的子进程并等待最多 10 秒，再停止采样线程。

`max_generate_time_sec` 与 `trial_timeout_sec` 含义不同：前者是业务可用性软阈值，后者是防止进程永久挂起的硬保护。

## 9. 内存采样与估算

### 9.1 采样来源

父进程的 `_MemorySampler` 默认每 0.5 秒采样：

- 系统 RAM：`psutil.virtual_memory()`；
- GPU 内存：Windows 下仓库内的 `get_gpu_memory_total()`；
- 当前值与运行期间峰值。

在共享内存 iGPU 环境中，GPU 使用百分比按以下方式计算：

$$
peak\_gpu\_pct = \frac{peak\_gpu\_gb}{system\_ram\_total\_gb} \times 100\%
$$

分母是系统总 RAM，不是离散显卡 VRAM。这是该组件面向 Intel iGPU 共享内存场景的特定口径。

### 9.2 权重与 KV-cache 差分

记：

- $M_0$：spawn 前系统内存基线；
- $M_L$：收到 `loaded` 后的系统内存；
- $M_P$：试验期间采样峰值。

则实现采用：

$$
M_{weight}=\max(0, M_L-M_0)
$$

$$
M_{kv}=\max(0, M_P-M_L)
$$

同时记录 $M_P$ 为系统高水位。RAM 和 GPU 分别进行同样计算，结果保留两位小数。

磁盘权重 `weight_disk_gb` 则递归累加模型目录下所有 `.bin` 文件大小，它是稳定参考值，不依赖试验是否成功加载。

### 9.2.1 理论 KV 大小与倍数诊断（`expected_kv_gpu_gb` / `kv_overhead_ratio`）

`M_kv` 是系统级实测增量，包含真实 KV-cache 之外的一切 loaded-后增长（见 §9.4）。为了不必每次靠人工翻 `config.json` 才能判断“这个数字是否合理”，`_theoretical_kv_bytes_per_token()`（`validate_long_context.py`）从模型自身导出的 `config.json` 计算一个架构层面的理论参考值：

$$
B_{token} = 2 \times L_{full} \times H_{kv} \times D_{head} \times b_{dtype}
$$

其中 $L_{full}$ 是真正需要随 token 数增长 KV-cache 的层数，$H_{kv}$、$D_{head}$ 来自模型配置的 `num_key_value_heads` / `head_dim`，$b_{dtype}$ 默认取 2（假设 fp16 KV-cache，因为工具本身无法读取运行时实际精度，这是一个声明的假设而非实测值）。

**混合线性注意力架构的处理**：`Qwen/Qwen3.5-9B` 与 `Qwen/Qwen3.6-35B-A3B` 的 `config.json`（`text_config.layer_types`）声明的不是均匀的 transformer，而是 3:1 交替的 `linear_attention` / `full_attention` 混合架构（类似 Qwen3-Next 的 Gated-DeltaNet 设计）：只有 `full_attention` 层需要随 token 数增长的传统 KV-cache，`linear_attention` 层理论上只维持一个不随长度增长的固定大小（O(1)）递归/SSM 状态。因此：

- 若 `layer_types` 存在，$L_{full}$ 只统计其中标记为 `full_attention` 的层数；
- 若 `layer_types` 不存在（普通稠密 transformer），$L_{full}$ 等于全部层数（与旧的隐含假设一致）；
- 若配置缺少 `num_hidden_layers` / `num_key_value_heads` / `head_dim` 等必要字段（导出格式不认识的架构），函数返回 `None`，调用方据此跳过该诊断而不是抛异常。

VLM 导出（本工具所有默认候选模型都是）把上述字段嵌套在顶层 `config.json` 的 `text_config` 下而非顶层本身，因此实现读取 `config.get("text_config", config)`，同时兼容纯 LLM 导出（字段在顶层）。

每次试验若 `kv_bytes_per_token` 可计算，则按 `prompt_tokens` 换算出 `expected_kv_gpu_gb`，并计算 `kv_overhead_ratio = kv_gpu_gb / expected_kv_gpu_gb`，一并写入 `trials.csv`、`summary.json` 与 `summary.md`；`summary.md` 在比值达到 `_KV_OVERHEAD_RATIO_NOTE_THRESHOLD`（默认 3x）时，会在 Notes 列直接标注为已知的上游缓存效率问题而不是笼统的容量说明。

这个比值**只是诊断信息**，不会改变 `_passed()` / `_classify_failure()` 的判定——该工具的定位始终是”装不装得下”，不是”效率是否合理”，倍数异常本身不构成容量失败。经验参考：对 `Qwen/Qwen3.5-9B` 用本地已转换的 IR 计算，实测 `kv_gpu_gb` 相对理论值稳定在约 **12.9 倍**（8K 到 120K token 全程一致）。

**一个已被证伪的解释，记录在此避免重蹈覆辙**：早期版本在这里引用过”OpenVINO 2026.2 发行说明中一个已知问题——Linear Attention 模型（如 Qwen3.5/Qwen3.6）配合 prefix caching 会消耗过量内存”来解释这个 12.9 倍。这个已知问题确实存在（可查 OpenVINO Model Server 关于 `cache_interval_multiplier` 参数的发行说明），但它的前提是**启用了 continuous batching 的 prefix caching**，而本工具的触发路径并不满足这个前提：`trial_runner.py::_load_pipeline()` 调用 `LLMPipeline`/`VLMPipeline` 时没有传入 `scheduler_config`、`ATTENTION_BACKEND=PA`，也没有请求 speculative decoding 或 prompt lookup；核对 OpenVINO GenAI 自身的后端选择逻辑（`utils.cpp::explicitly_requires_paged_attention()`）后确认，缺少这些属性时它必然回退到默认的**有状态单序列后端**，而不是 continuous batching/分页注意力/prefix caching 那条路径——导出的 IR 里 `cache_params.past.*` 用 `ReadValue`/`Assign` 的有状态变量表示（而不是 PagedAttention 专用算子）也印证了这一点。也就是说，被引用的那个已知问题的触发条件在这里根本不成立，不能作为这 12.9 倍的解释。

站得住脚的原因是**统计口径不对齐**，不是某个具体的上游 bug：`expected_kv_gpu_gb` 只按会随 token 数增长的持久态缓存层（`full_attention`，8 层）计算；而 `kv_gpu_gb`（即 §9.4 的 $M_{kv}$）按设计统计 loaded 之后的**全部**显存增长，这自然包含 prefill 阶段全部 32 层（含 24 个 `linear_attention` 层）对每个 prompt token 的 Q/K/V 投影、MLP 激活等工作显存——这些层虽然不持久保留随 token 数增长的 KV-cache，但 prefill 时仍要对每个 token 完整计算一遍，其工作显存与「全部层数 × token 数」成正比，而不是「持久态层数 × token 数」。两个数字统计的对象不同，比值偏大是结构性的，不足以单凭这个比值把差距归因于某个具体的上游缺陷；真要进一步拆解，需要在 prefill 刚完成、decode 结束这两个时间点分别打点采样（本工具目前没有做这一级拆分）。

### 9.3 为什么在父进程采样

父进程采样是故障容忍设计：即使子进程因 native 崩溃、OOM 或超时被杀，采样线程仍能保留此前峰值。若把采样放在子进程内，最值得诊断的失败路径反而可能没有结果。

### 9.4 测量口径限制

这些数值是**系统级近似值**，不是精确的进程归因：

- 试验期间其他进程的内存变化会进入差分；
- 0.5 秒采样可能漏过更短的瞬时峰值；
- `loaded` 消息存在队列传输延迟；
- spawn 子进程、Python runtime、tokenizer 和 pipeline 辅助对象也计入“权重差分”；
- `kv_*` 实际表示 loaded 之后到峰值的全部增量，不只包含 KV-cache；
- GPU 采样不可用时返回 0，相关百分比可能为 `None`；
- `_delta()` 将负差值钳制为 0，避免背景释放内存产生负占用。

因此报告适合容量比较与瓶颈定位，不应当作精确显存 profiler 的替代品。

## 10. 通过策略与失败分类

### 10.1 PASS 条件

`_passed()` 要求以下条件全部成立：

```text
load_ok
AND generate_ok
AND generated_tokens > 0
AND NOT resource_limit_reached
```

`resource_limit_reached` 不是简单的超时判断，而是两个信号同时成立：

```text
generate_time_s > max_generate_time_sec
AND gpu_memory_at_limit is True
```

因此：

| 生成时间 | GPU 内存压力 | 结果 |
|---|---|---|
| SLA 内 | 任意 | 不因资源策略失败 |
| 超过 SLA | 未达压力线 | 仍可 PASS，但报告 latency breach |
| 超过 SLA | 达到压力线 | FAIL，分类 `too_slow` |

这种组合策略用于区分“模型本身较慢”和“共享内存耗尽导致的 paging/thrashing”。单独变慢不被视为容量上限，变慢且内存饱和才被视为不具备实际可用性。边界是严格大于：`generate_time_s == max_generate_time_sec` 仍通过。

### 10.2 失败分类优先级

`_classify_failure()` 按以下顺序分类：

1. 原始错误为 `timeout` 或 `crashed:*`；
2. 加载失败：OOM 为 `oom`，否则 `load_error`；
3. 生成失败：OOM 为 `oom`，`no_output` 单独保留，否则 `generate_error`；
4. 生成 token 数为 0：`no_output`；
5. 触发组合资源阈值：`too_slow`；
6. 无法归类：`unknown`。

注意：`special_tokens_only`、`invalid_characters`、`no_semantic_output` 和 `repetitive_output` 会令 `generate_ok=False`，最终统一归入 `generate_error`，详细原因保留在 `error` 字段中。

## 11. 模型扫描与边界细化

### 11.1 阶梯扫描

`_sweep_model()` 对排好序的 `context_steps_tokens` 逐项运行：

```mermaid
flowchart TD
    A[检查 IR] -->|缺失| M[返回 missing_ir]
    A -->|就绪| B[运行当前 token 阶梯]
    B --> C[立即追加 trials.csv]
    C --> D{_passed?}
    D -->|是| E[更新 max_stable 与指标]
    E --> F{还有阶梯?}
    F -->|是| B
    F -->|否| G[达到最高配置阶梯]
    D -->|否| H[记录 failure_reason 并停止]
    H --> I{--refine 且已有成功点?}
    I -->|否| J[形成模型报告]
    I -->|是| K[在最后成功与首次失败间二分]
    K --> J
    G --> J
```

第一次失败后立即停止，依赖“上下文越长，容量压力不会下降”的单调性假设。这样避免在已知不可承载的更高 token 点上浪费时间或反复冲击驱动。

如果首个阶梯就失败，`max_stable_context=0`，且没有可用下界，因此不会执行 refine。

### 11.2 `--refine` 二分细化

当存在最后成功值 $L$ 和首次失败值 $H$ 时，最多额外执行 3 次：

$$
M=\left\lfloor\frac{L+H}{2}\right\rfloor
$$

- $M$ 通过：令 $L=M$；
- $M$ 失败：令 $H=M$；
- 当区间宽度不大于“最小配置阶梯的八分之一”时提前结束。

每次 refine 试验也立即追加到 `trials.csv`。该过程只收紧区间，不追求 token 级精确边界；最终 `max_stable_context` 是已观测通过值，而不是推测值。

### 11.3 dry-run

`--dry-run` 使用由模型名确定的伪上限生成稳定结果：

- 权重内存固定；
- KV 内存随 token 数线性增加；
- 超过伪上限时模拟 `generate:oom`；
- 不加载模型、不使用 OpenVINO 或 GPU。

它用于验证配置解析、扫描、refine、CSV 和 summary 管道，不验证真实硬件容量。

## 12. 数据模型与输出

### 12.1 单次试验结果

子进程首先形成基础结果：

```json
{
  "tokens_requested": 160000,
  "load_ok": true,
  "load_time_s": 12.3,
  "generate_ok": true,
  "prompt_tokens": 160000,
  "generated_tokens": 64,
  "generate_time_s": 45.2,
  "error": null
}
```

父进程再补充：

- 权重、KV 和峰值 RAM/GPU；
- `tokens_per_second`；
- SLA 与 GPU 压力阈值；
- `latency_limit_exceeded`；
- `peak_gpu_pct` 与 `gpu_memory_at_limit`；
- `expected_kv_gpu_gb` 与 `kv_overhead_ratio`（§9.2.1，模型 `config.json` 可解析时才有值，否则为 `None`）；
- CSV 中的模型、设备、权重格式、磁盘权重和最终状态。

### 12.2 `trials.csv`

每次试验完成后立即以 append 模式写入。这保证长时间扫描中途异常时，之前的数据仍保留。

实现影响是：同一输出目录重复运行会将新行继续追加到旧文件，而不会自动清空或添加 run id。做正式对比前应使用独立输出目录，或明确归档旧 CSV，避免不同硬件、配置或日期的数据混在一起。

### 12.3 `summary.json`

扫描结束后覆盖写入，包含：

- 生成时间；
- 目标 token、probe token、生成 SLA；
- 当前硬件信息；
- 每个模型的最大稳定上下文、是否达标、最大稳定点内存和失败原因。

内存字段来自“最大已通过点”，不是首次失败点。`failure_reason` 则来自其后的首次失败，因此一个已经达到目标的模型仍可能有失败原因，表示工具继续探测到了更高容量边界。

### 12.4 `summary.md`

面向人工阅读，展示每个模型的设备、权重格式、最大稳定上下文、是否达到目标、磁盘权重、峰值内存和说明。

`meets_target` 的计算为：

$$
meets\_target = max\_stable\_context \ge target\_context\_tokens
$$

由于 `max_stable_context` 只取实际测试过的点，如果阶梯没有包含目标附近的足够密度，报告会偏保守。例如最后通过 144K、下一点 176K 失败，并不能直接证明 160K 失败；应把 160K 加入阶梯或使用 refine。

## 13. 完整调用链

```text
main()
├── _parse_args()
├── _preflight_environment_check()       # 非 dry-run
├── _load_settings()
├── os.makedirs(output_dir)
├── _safe_platform_info()
│   └── get_platform_and_model_info()
├── for model_name in candidate_models
│   └── _sweep_model()
│       ├── _model_ir_dir()
│       ├── _ir_ready()
│       ├── _weight_disk_gb()
│       └── for tokens in context_steps_tokens
│           └── _run_one()
│               ├── _run_trial_dry_run()
│               └── _run_trial_subprocess()
│                   ├── _read_mem()              # baseline
│                   ├── _MemorySampler.start()
│                   ├── spawn trial_runner.run_trial()
│                   │   ├── _load_tokenizer()
│                   │   ├── _load_pipeline()
│                   │   ├── queue.put(loaded)
│                   │   ├── build_context_prompt()
│                   │   │   ├── measure_template_overhead()
│                   │   │   └── build_text_of_token_length()
│                   │   ├── pipe.generate()
│                   │   ├── _validate_generated_output()
│                   │   └── queue.put(done)
│                   ├── timeout/crash handling
│                   └── merge memory metrics
│           ├── _append_trial_row()
│           ├── _passed()
│           └── optional _refine_boundary()
└── _write_summary()
    ├── summary.json
    └── summary.md
```

## 14. 测试设计

现有测试集中验证不依赖真实硬件的确定性逻辑：

| 测试文件 | 覆盖点 |
|---|---|
| `test_context_validation_context_builder.py` | 0 token、固定长度构造、160K 大输入、模板开销排除 user content、完整 prompt 命中目标。 |
| `test_context_validation_output.py` | 接受自然语言；拒绝标点、特殊 token 和单字符重复输出。 |
| `test_context_validation_policy.py` | 正常通过、慢但无 GPU 压力仍通过、慢且内存饱和失败、SLA 等号边界通过。 |
| `test_context_validation_kv_estimate.py` | 无 `layer_types` 的稠密模型全层计数、Qwen3.5-9B 形态的混合线性注意力只统计 `full_attention` 层、VLM 的 `text_config` 嵌套读取、缺字段返回 `None`、自定义 KV 精度字节数。 |

测试使用轻量 `FakeTokenizer`，因此不会下载模型或引入 OpenVINO 环境依赖。

推荐验证命令：

```powershell
Set-Location smart-classroom
python -m unittest components.tests.test_context_validation_context_builder components.tests.test_context_validation_output components.tests.test_context_validation_policy components.tests.test_context_validation_kv_estimate
```

还可以执行以下 dry-run 作为编排层集成检查：

```powershell
.\components\llm\context_validation\run_validate_long_context.ps1 --dry-run --refine
```

当前自动化测试没有覆盖的高风险区域包括：真实 `multiprocessing spawn` 生命周期、queue 事件丢失、Windows GPU counter、OpenVINO LLM/VLM pipeline 选择、真实 tokenizer 回退，以及报告在多次运行下的 CSV 追加行为。

## 15. 核心设计思想总结

### 15.1 将“模型能力”与“机器容量”分离

模型配置声明支持某个上下文窗口，不代表目标机器有足够内存完成该长度的 prefill。组件通过真实 OpenVINO 推理把理论上限转换为设备相关的实测上限。

### 15.2 用最小输出换取最大容量信号

仅 decode 64 个 token，把主要成本集中在长上下文 prefill。这样既证明模型能从 prefill 进入 decode，又不为生成完整摘要付出与容量判断无关的时间。

### 15.3 用进程边界处理 native 失败

OpenVINO、GPU 驱动和大内存分配的失败不一定能被 Python 安全恢复。独立进程让退出本身成为资源回收与故障隔离机制。

### 15.4 用阶段事件分解内存

`loaded` 和 `done` 两个里程碑把内存曲线粗分为“模型权重驻留”和“prefill/decode 增量”，以低实现成本提供比单一峰值更有解释力的诊断。

### 15.5 将软 SLA 与压力证据组合

单独的慢可能是模型特性，单独的高内存也未必不可用。两者同时出现更接近共享内存系统开始 thrashing 的现象，因此才定义为容量失败。

### 15.6 保留原始证据，再生成结论

每个扫描点先写 CSV，再计算模型级结论。原始数据可以用于重新解释阈值、观察趋势和排查异常；summary 只负责给出当前策略下的决策结果。

## 16. 已知限制与演进建议

### 16.1 当前限制

1. **不是质量测试**：不验证长距离事实召回或摘要正确性。
2. **依赖单调性**：一次失败后不再测试更长阶梯，偶发驱动错误可能低估上限。
3. **系统级内存噪声**：权重和 KV 数据是近似差分。
4. **GPU 指标平台相关**：当前采样器主要面向 Windows Intel iGPU。
5. **OOM 文本启发式**：未包含的新 runtime 错误文本可能被归为普通异常。
6. **输出校验较弱**：能排除明显垃圾，但不能确认语义质量。
7. **CSV 无 run id**：复用目录会混合多次运行的数据。
8. **配置校验有限**：空阶梯、重复值、非法阈值不会在加载时给出专门错误。
9. **单次观测**：每个 token 点默认只跑一次，无法估计抖动和稳定性分布。
10. **IR 检查规则有隐含布局假设**：ready 检查递归，pipeline 加载检查根目录。

### 16.2 可选演进方向

- 为每次运行生成 `run_id`，CSV 增加时间、配置哈希和硬件指纹；
- 增加 `repetitions` 与通过率策略，区分稳定上限和偶发成功；
- 对配置做结构化校验，并强制目标 token 出现在扫描点中；
- 记录完整内存时间序列，辅助识别 prefill 峰值和 thrashing；
- 将 OOM 分类扩展为 runtime/driver 错误码优先、文本匹配兜底；
- 为父子进程协议增加独立集成测试，模拟 loaded 后崩溃、无 done、硬超时等路径；
- 将“容量验证”和单独的 needle-in-a-haystack/真实摘要质量验证组合成部署验收流程，但继续保持结果维度分离。

## 17. 关键源码索引

| 主题 | 符号 |
|---|---|
| CLI 入口 | `validate_long_context.main`, `_parse_args`, `_load_settings` |
| 模型扫描 | `_sweep_model`, `_run_one`, `_refine_boundary` |
| 子进程控制 | `_run_trial_subprocess` |
| 内存采样 | `_read_mem`, `_MemorySampler`, `_delta` |
| 理论 KV 估算 | `_load_model_config`, `_theoretical_kv_bytes_per_token` |
| 策略判断 | `_passed`, `_resource_limit_reached`, `_classify_failure` |
| 单次推理 | `trial_runner.run_trial` |
| Pipeline 选择 | `trial_runner._load_pipeline` |
| Tokenizer 回退 | `trial_runner._load_tokenizer` |
| 输出检查 | `trial_runner._validate_generated_output` |
| Prompt 定长 | `context_builder.build_context_prompt`, `build_text_of_token_length` |
| 报告输出 | `_append_trial_row`, `_write_summary` |

## 18. 结论

`context_validation` 的本质是一个面向大模型长上下文的硬件压力探针。它通过真实模型、真实 tokenizer 和真实 OpenVINO pipeline 施加负载，同时通过独立子进程、父进程超时控制和阶段化内存采样，把可能导致 OOM、挂起或驱动异常的试验转化为可恢复、可比较、可审计的扫描结果。

其核心结论应按以下方式解读：

> `max_stable_context=N` 表示在本次运行的模型、权重格式、设备、驱动、系统负载、SLA 和采样策略下，`N` 是已实际观测通过的最大 token 点；它既不是模型声明的理论窗口，也不是模型长文本理解质量的证明。

这一边界定义清楚后，该组件可以可靠承担模型选型和部署前容量规划，而语义质量、业务正确性与生产并发能力应由其他专项测试补充。