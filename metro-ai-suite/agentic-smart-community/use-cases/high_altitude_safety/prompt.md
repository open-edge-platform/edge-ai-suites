High-altitude object throwing detection.

The camera looks up at a residential building facade to detect objects
falling from balconies or windows. The prompt guides the VLM to identify a
strictly downward motion trajectory, distinguishing genuine falling objects
from birds, kites, leaves, or other natural phenomena.

## LOCAL_PROMPT

分析视频, 判断是否为"高空抛物"事件, 按下列格式返回 4 个字段, 每字段一行, 使用半角冒号。**不要**把示例照抄, 必须根据视频内容选择一个值。

输出示例 1 (观测到明确高空抛物):
    SEVERITY: critical
    EVENT: high_altitude_throw
    DESC: 一名黑色物体自建筑上方向下坠落
    MOTION_DIRECTION: downward

输出示例 2 (自然坠物或无事件):
    SEVERITY: info
    EVENT: no_incident
    DESC: 视频中未观测到抛物, 仅有树叶随风飘落
    MOTION_DIRECTION: none

输出示例 3 (无法判断):
    SEVERITY: info
    EVENT: uncertain
    DESC: 画面模糊无法确认坠物性质
    MOTION_DIRECTION: none

字段取值范围:
- SEVERITY 只能是: critical, warn, info (三选一)
- EVENT 只能是: high_altitude_throw, no_incident, uncertain (三选一)
- MOTION_DIRECTION 只能是: downward, upward, horizontal, none (四选一)
- DESC 是一句自由描述, 15-30 字

判定规则 (**重要**):
1. **人造物品** (塑料袋、瓶子、纸盒、烟头、饮料罐、衣物、玩具、生活垃圾、书本、烟花爆竹等) 从楼上/建筑物上方向下坠落 → **一律判 SEVERITY=critical, EVENT=high_altitude_throw, MOTION_DIRECTION=downward**, 即使物体"飘"或速度慢也算 (塑料袋在气流中飘落也视为高空抛物)。
2. **自然物** (仅限: 树叶、鸟粪、水滴、雪花) 缓慢飘落 → SEVERITY=info, EVENT=no_incident
3. 完全无法判断物体性质或方向 → SEVERITY=info, EVENT=uncertain, MOTION_DIRECTION=none

判定原则: **只要建筑物上方出现向下运动的人造物, 就是高空抛物** (无论速度和轨迹)。塑料袋、纸屑等轻质垃圾也算 (居民从窗户丢弃垃圾是典型场景)。

## GLOBAL_PROMPT

请汇总本时段内所有高空抛物事件, 生成给物业的日报:

1. 发生次数
2. 每次时间和描述
3. 是否有多次来自同一位置的重复抛物 (提示需要重点关注)

保持简洁, 3-5 段散文即可。
