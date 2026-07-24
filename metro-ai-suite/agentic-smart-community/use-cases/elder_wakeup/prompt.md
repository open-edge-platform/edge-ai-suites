Dynamic task registration content for elder_wakeup_monitor.

Single task name shared between realtime detection and the weekly report:
  - LOCAL_PROMPT      — per-clip wakeup detection (3-line EVENT/WAKEUP_TIME/DESC)
  - GLOBAL_PROMPT     — weekly report commentary (TWO short prose lines:
                        overview + suggestion). The plugin assembles the
                        actual table + counts deterministically and only
                        asks the VLM for the prose.
  - MACRO_CHUNK_PROMPT — same shape as GLOBAL (the report is one block).
  - T_MINUS_1_PROMPT  — context from previous chunk during realtime detection

Phase-2 tasks behind this file:
  - Task 1: Track wakeup time; alert caregiver if deviation > 30min (handled
            in realtime via LOCAL_PROMPT + plugin rule-engine `late_wakeup`).
  - Task 2: Weekly wakeup summary report (the plugin's daily-report tool
            renders the table + counts in TS, then calls this task in
            caption-only mode for two prose lines, then stitches).

This file is read by tools/register_task.py and POSTed to the VLM service
via /v1/tasks for dynamic registration.

Template placeholders:
  {question}      — runtime user prompt (from configs/*.yaml -> vlm.prompt_path)
  {st_tm}         — chunk start time (seconds), auto-filled by service
  {end_tm}        — chunk end time (seconds), auto-filled by service
  {dur}           — previous chunk duration (seconds)
  {past_summary}  — previous chunk summary text

## GLOBAL_PROMPT

##任务:
将下面 SRT 中"老人本周每日起床观测"汇总为一份家人可读的中文周报。

##SRT 标签词表（标签里的日期/星期/时间/数字是权威信息，**直接引用**，不要换算或自行计算）:
- `[meta:baseline=HH:MM grace=Nmin late_after=HH:MM]` = 本周配置元信息（**只出现 1 次，在 SRT 第一块**）。
  其中 `baseline` 是预期起床时间，`grace` 是宽限分钟数，`late_after` 是晚起阈值。
  概览段引用基线时**必须用 meta 块里的数字**（baseline=HH:MM），不要写死"07:30"或自己猜。
- `[wakeup:MM/DD 周X HH:MM][on_time]`        = 该日按时起床。
- `[wakeup:MM/DD 周X HH:MM][late_wakeup:warn]` = 该日起床偏晚，触发了 late_wakeup 告警。
- `[no_wakeup:MM/DD 周X][warn]`              = 该日未观察到起床（兜底告警）。
- `[no_data:MM/DD 周X]`                       = 该日无监控记录（请如实写"无记录"）。

除 meta 块之外，**每一条 SRT 块代表一天**。SRT 中有 N 个 wakeup/no_wakeup/no_data 块就是 N 天，**每一天都必须在"每日时间表"里出现一行，缺一不可**（meta 块不计入"每日时间表"）。

##请严格按以下模板输出（无内容的板块整块删除）:

本周起床概览：<两三句话总结本周节奏，引用 MM/DD 周X；点出晚起的日期；可在概览中提到本周预期基线（直接引用 meta 块的 `baseline=HH:MM`）。不要重复列出每一天。>

每日时间表：
| 日期 | 起床时间 | 状态 |
|---|---|---|
| MM/DD 周X | HH:MM | 按时 / 晚起 ⚠️ / 未起床 ⚠️ / 无记录 |
| ... | ... | ... |
（**SRT 中每一个块都要对应一行，按 MM/DD 升序**）

趋势建议：<一句话给家人具体可执行的关注点；整体平稳就写"本周节奏稳定，继续保持。"。>

##硬规则（违反任意一条都算输出错误）:
1. **每一条 SRT 块都必须出现在"每日时间表"里**（自检：表里行数 = SRT 块数）。
2. 状态列只有四种用词：「按时」「晚起 ⚠️」「未起床 ⚠️」「无记录」，**严格按标签 verdict**。
3. **禁止编造任何分钟数**（"晚 15 分钟"、"早 10 分钟"、"晚 30 分钟" 等都是错误）——SRT 没给具体偏差，你也不知道阈值，需要描述偏差时只说"偏晚 / 晚起"。
4. 引用日期/星期必须照标签原样写 MM/DD + 周X，不要换算或猜测星期。
5. `[no_data:...]` 行的"起床时间"列写 `—`，"状态"列写"无记录"。
6. 不要在输出里写 `[wakeup:...]` `[on_time]` `[late_wakeup:warn]` 这些原始标签。

用户提问: {question}

##待总结内容（每个 SRT 块 = 一天观测）:

## MACRO_CHUNK_PROMPT

##任务:
将下面 SRT 中"老人本周每日起床观测"汇总为一份家人可读的中文周报。

##SRT 标签词表（标签里的日期/星期/时间/数字是权威信息，**直接引用**，不要换算或自行计算）:
- `[meta:baseline=HH:MM grace=Nmin late_after=HH:MM]` = 本周配置元信息（**只出现 1 次，在 SRT 第一块**）。
  其中 `baseline` 是预期起床时间，`grace` 是宽限分钟数，`late_after` 是晚起阈值。
  概览段引用基线时**必须用 meta 块里的数字**（baseline=HH:MM），不要写死"07:30"或自己猜。
- `[wakeup:MM/DD 周X HH:MM][on_time]`        = 该日按时起床。
- `[wakeup:MM/DD 周X HH:MM][late_wakeup:warn]` = 该日起床偏晚，触发了 late_wakeup 告警。
- `[no_wakeup:MM/DD 周X][warn]`              = 该日未观察到起床（兜底告警）。
- `[no_data:MM/DD 周X]`                       = 该日无监控记录（请如实写"无记录"）。

除 meta 块之外，**每一条 SRT 块代表一天**。SRT 中有 N 个 wakeup/no_wakeup/no_data 块就是 N 天，**每一天都必须在"每日时间表"里出现一行，缺一不可**（meta 块不计入"每日时间表"）。

##请严格按以下模板输出（无内容的板块整块删除）:

本周起床概览：<两三句话总结本周节奏，引用 MM/DD 周X；点出晚起的日期；可在概览中提到本周预期基线（直接引用 meta 块的 `baseline=HH:MM`）。不要重复列出每一天。>

每日时间表：
| 日期 | 起床时间 | 状态 |
|---|---|---|
| MM/DD 周X | HH:MM | 按时 / 晚起 ⚠️ / 未起床 ⚠️ / 无记录 |
| ... | ... | ... |
（**SRT 中每一个块都要对应一行，按 MM/DD 升序**）

趋势建议：<一句话给家人具体可执行的关注点；整体平稳就写"本周节奏稳定，继续保持。"。>

##硬规则（违反任意一条都算输出错误）:
1. **每一条 SRT 块都必须出现在"每日时间表"里**（自检：表里行数 = SRT 块数）。
2. 状态列只有四种用词：「按时」「晚起 ⚠️」「未起床 ⚠️」「无记录」，**严格按标签 verdict**。
3. **禁止编造任何分钟数**（"晚 15 分钟"、"早 10 分钟"、"晚 30 分钟" 等都是错误）——SRT 没给具体偏差，你也不知道阈值，需要描述偏差时只说"偏晚 / 晚起"。
4. 引用日期/星期必须照标签原样写 MM/DD + 周X，不要换算或猜测星期。
5. `[no_data:...]` 行的"起床时间"列写 `—`，"状态"列写"无记录"。
6. 不要在输出里写 `[wakeup:...]` `[on_time]` `[late_wakeup:warn]` 这些原始标签。

用户提问: {question}

##待总结内容（每个 SRT 块 = 一天观测）:

## LOCAL_PROMPT

##任务:
你是一个老年人起床监测AI。分析这段卧室监控视频片段，判断老人是否正在起床。
开始时间: {st_tm} 秒
结束时间: {end_tm} 秒
用户提问: {question}

##状态定义（必须严格按此判断）:
get_up — 以下任一情况:
  - 老人从躺姿坐起并将双腿移至床沿
  - 老人从床上站起来
  - 老人明确走离床铺

in_bed_awake — 以下任一情况:
  - 老人在床上坐起但未下床
  - 老人在床上翻身、伸展、或有较明显动作
  - 老人睁眼坐在床上但腿仍在被子里

still_sleeping — 以下情况:
  - 老人躺在床上，几乎无运动或仅有极微小动作

empty — 以下情况:
  - 画面中床铺可见但无人
  - 画面全黑或无法辨识内容

##关键判断原则:
- 坐到床沿+双脚落地 = get_up，不需要等完全站立
- 仅坐起但腿仍在被子里 = in_bed_awake
- 如果不确定是 get_up 还是 in_bed_awake，观察双腿是否移出床面

##输出格式（严格遵守，只输出以下3行）:
EVENT: get_up 或 in_bed_awake 或 still_sleeping 或 empty
WAKEUP_TIME: 起床动作开始的视频秒数（无则写 none）
DESC: 一句话描述画面中老人的具体姿态和动作

##禁止事项:
- 不要输出JSON格式
- 不要加markdown符号或方括号
- 不要写分析过程或逐条排查
- 只输出EVENT、WAKEUP_TIME、DESC三行，无其他内容

## T_MINUS_1_PROMPT

##上下文（前{dur}秒的判断结果，仅供参考，不要复制到输出中）:
开始时间: {st_tm} 秒
结束时间: {end_tm} 秒
{past_summary}

注意：根据上一片段的上下文，独立判断当前片段。如果上一片段老人开始起床动作，当前片段应重点观察是否完成了下床。
