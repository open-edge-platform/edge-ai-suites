Dynamic task registration content for fridge_monitor (Chinese).

Pre-staged for future use; not yet on the registration path. When the
multilevel-video-understanding service drops its built-in
``refrigerator_monitor`` + ``daily_report`` tasks, this single merged file
takes over both jobs under one task name.

Two execution modes share this single task name:

  1. **Realtime narrative summarization** (worker → /v1/summary on each
     motion clip).
     - Only LOCAL_PROMPT is invoked (single chunk per motion clip).
     - LOCAL produces a free-form Chinese narrative covering door state,
       items taken/put back, person actions, anomalies — the same shape
       the existing fridge dashboard already consumes.
     - No structured SEVERITY/EVENT contract; the fridge plugin parses the
       narrative downstream.

  2. **Daily-report aggregation** (smarthome-video plugin daily_report tool
     → /v1/summary in caption-only mode with SRT containing the day's
     [motion] / [static] events).
     - LOCAL is skipped (caption-only feeds pre-built SRT).
     - MACRO_CHUNK_PROMPT + GLOBAL_PROMPT consume the SRT and emit a
       structured report (activity overview / inventory / suggestions /
       habit analysis / dietary advice).

Template placeholders (auto-filled by the video-summary service):
  {question}      — optional user prompt
  {st_tm}         — chunk start time in seconds
  {end_tm}        — chunk end time in seconds
  {dur}           — previous chunk duration (T_MINUS_1)
  {past_summary}  — previous chunk summary (T_MINUS_1)

## GLOBAL_PROMPT

##任务:
将以下冰箱事件汇总为简短报告。
**重要：以下 SRT 中的时间戳（HH:MM:SS）是 24 小时制的真实北京时间，不是视频播放时间。例如：06:30 = 早晨6:30, 12:15 = 中午12:15, 17:03 = 下午5:03, 22:00 = 晚上10:00。请据此准确判断用户活动时段**
**事件类型：每条 SRT 条目以 [motion] 或 [static] 开头。[motion] = 冰箱门被打开，统计开门次数时只计这类。[static] = 无人使用时段，不计为开门。**
用户提问: {question}

##请严格按以下模板输出（替换尖括号内容，无内容的板块整块删除）:

今日冰箱活动概括：<两三句话概括主要活动，包括涉及的物品种类和使用时段特征>

当前库存（根据今日活动估算）：
- <物品A>：<剩余数量> — <状态：充足 / 不足 / 已取完>
- <物品B>：<剩余数量> — <状态>

建议：<一句话建议>

用户习惯分析：<一句话，说明高峰时段和频率>

饮食建议：<一句话健康建议>

##示例输出:

今日冰箱活动概括：主要取用了牛奶和酸奶，集中在早晨和傍晚两个时段，傍晚取用频率较高。

库存提醒：
- 牛奶 剩余1盒，建议补充
- 酸奶 已取完

用户习惯分析：开门集中在早晨7-8点和傍晚18-19点，早晨以取早餐食品为主。

##规则:
- 禁止列出每次开门的时间和详情
- 每个板块最多一句话
- 无事件则只输出"未检测到开门事件"

##待总结内容:
以下事件用 ">|<" 分开。

## MACRO_CHUNK_PROMPT

##任务:
用2-3句话汇总该时段冰箱使用情况。
**注意：事件中的时间戳是北京时间真实钟表时间（如 17:03 = 下午5:03）。**
**事件类型：每条 SRT 条目以 [motion] 或 [static] 开头。[motion] = 冰箱门被打开，统计开门次数时只计这类。[static] = 无人使用时段，不计为开门。**
开始时间: {st_tm} 秒
结束时间: {end_tm} 秒
用户提问: {question}

##输出格式（严格2-3句话）:
第1句：涉及物品：<物品名+数量+取出/放入>。
第2句：<剩余量变化>。
第3句（如有）：<异常行为>。

##示例输出:
涉及物品：牛奶取出2盒、可乐放入1瓶。牛奶剩余1盒。

##规则:
- 合并重复物品，只写汇总数量
- 禁止逐条列出每次开门
- 不输出"[" "]"

##待总结内容:
以下子事件用 ">|<" 分开。

## LOCAL_PROMPT

##任务:
你正在分析一段智能家居场景中的冰箱监控视频片段。请详细描述该片段中与冰箱相关的所有活动。
开始时间: {st_tm} 秒
结束时间: {end_tm} 秒
用户提问: {question}

##指南:
- 重点关注以下内容：
  1. 冰箱门状态：门是否打开、关闭、半开，门的开合角度变化。
  2. 物品交互：详细描述从冰箱中取出或放入的每一件物品，包括物品类型（食物、饮料、容器等）、颜色、形状、包装特征。
  3. 冰箱内部：如果冰箱内部可见，描述可见的物品摆放情况。
  4. 人物动作：描述人物在冰箱前的具体动作（弯腰、伸手、翻找、站立等待等）。
- **重要** 输出尽量简洁，包含以上描述的需要点，这些信息将用于后续的事件分析和异常检测。
- 如果画面中出现文字（如食品标签），请以原语言描述并在括号中提供翻译。
- 如果该片段中没有与冰箱相关的活动（如人物仅路过），也请如实描述画面内容。
- 摘要中不要包含 "[" 或 "]"。
- 输出中不要包含 "开始时间" 和 "结束时间"。

## T_MINUS_1_PROMPT

##上下文（前{dur}秒的判断结果，仅供参考，不要复制到输出中）:
开始时间: {st_tm} 秒
结束时间: {end_tm} 秒
{past_summary}

注意：根据上一片段中冰箱门的状态和出现的人物，在当前片段描述中保持连贯。不要把上一片段的内容复制到本次输出。
