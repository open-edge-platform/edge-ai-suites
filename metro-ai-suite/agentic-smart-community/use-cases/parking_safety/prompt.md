Parking violation detection for community / residential parking lots.

The camera monitors a shared parking area (fire lane, entrance, handicapped
spots, or general lot). The prompt guides the VLM to detect and classify
vehicles parked in restricted zones. Written following the "prompt writing
conventions" in
[docs/use-case-adapter.md](../../docs/use-case-adapter.md).

## LOCAL_PROMPT

分析视频, 判断是否存在"违章停车"事件。按下列格式返回 5 个字段, 每字段一行, 使用半角冒号。**不要**照抄示例, 必须根据视频内容选择一个值。

输出示例 1 (消防通道停车 — 违章):
    SEVERITY: critical
    EVENT: fire_lane_parking
    DESC: 一辆白色轿车停在消防通道内, 阻塞通道
    PARKING_ZONE: fire_lane
    MOTION_DIRECTION: none

输出示例 2 (占用无障碍车位):
    SEVERITY: warn
    EVENT: handicapped_spot_parking
    DESC: 一辆黑色 SUV 停在无障碍车位, 未见轮椅标识
    PARKING_ZONE: handicapped
    MOTION_DIRECTION: none

输出示例 3 (合法停车):
    SEVERITY: info
    EVENT: no_incident
    DESC: 车辆正常停放于停车位内
    PARKING_ZONE: normal
    MOTION_DIRECTION: none

输出示例 4 (无法判断):
    SEVERITY: info
    EVENT: uncertain
    DESC: 画面模糊或角度不佳, 无法判断停车合规性
    PARKING_ZONE: unknown
    MOTION_DIRECTION: none

字段取值范围:
- SEVERITY 只能是: critical, warn, info (三选一)
- EVENT 只能是: fire_lane_parking, entrance_blocking, handicapped_spot_parking, double_yellow_line_parking, no_incident, uncertain (六选一)
- PARKING_ZONE 只能是: fire_lane, entrance, handicapped, double_yellow_line, normal, unknown (六选一)
- MOTION_DIRECTION 只能是: none (违章停车通常无运动)
- DESC 是一句自由描述, 15-40 字, 说明车辆颜色 / 车型 / 位置

判定规则:
1. 车辆停放在**消防通道** (地面黄色 / 红色标识, "消防通道"字样, 应急车道)
   → SEVERITY=critical, EVENT=fire_lane_parking, PARKING_ZONE=fire_lane
2. 车辆停放**堵住小区出入口 / 单元门 / 车库入口**
   → SEVERITY=critical, EVENT=entrance_blocking, PARKING_ZONE=entrance
3. 车辆占用**无障碍车位** (地面有轮椅图标, 蓝色框线)
   → SEVERITY=warn, EVENT=handicapped_spot_parking, PARKING_ZONE=handicapped
4. 车辆停在**双黄实线区域**或**十字禁停区**
   → SEVERITY=warn, EVENT=double_yellow_line_parking, PARKING_ZONE=double_yellow_line
5. 车辆停放于正常划线车位内 → SEVERITY=info, EVENT=no_incident, PARKING_ZONE=normal
6. 完全无法判断 → SEVERITY=info, EVENT=uncertain, PARKING_ZONE=unknown

判定原则: 只要车辆停放位置属于"禁停区域" (无论时间长短), 就判违章。**关注地面标识和车位划线**, 忽略车辆颜色 / 车牌等无关信息。

## GLOBAL_PROMPT

请汇总本时段内所有违章停车事件, 生成给物业的日报:

1. 各类违章总数 (消防通道 / 出入口 / 无障碍位 / 双黄线)
2. 最严重的 3 起违章 (车辆特征 + 时间)
3. 是否有反复违章 (同一辆车 / 同一位置 3 次以上)

保持简洁, 3-5 段散文即可。
