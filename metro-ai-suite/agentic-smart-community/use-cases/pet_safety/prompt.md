## LOCAL_PROMPT
# 一句话任务目标
分析10秒家庭监控视频，识别宠物是否处于危险状态（如被卡住、试图逃离）或正常活动，并输出结构化事件报告。

# 输入说明
输入为10秒RTSP摄像头片段，需观察宠物在画面中的位置、动作及周围环境，判断是否存在被困、挣扎、攀爬门窗等异常行为，或正常的休息、玩耍、进食状态。

# 输出字段
- SEVERITY (critical|warn|info)
- EVENT (pet_stuck|pet_escape|pet_normal|no_incident)
- DESC (一句话中文描述)
- PET_ZONE (可选，记录宠物所在的具体区域，如“沙发下”、“阳台”、“厨房”)

# 输出示例 1
    SEVERITY: critical
    EVENT: pet_stuck
    DESC: 宠物头部卡在沙发缝隙中无法移动，正在剧烈挣扎
    PET_ZONE: 客厅沙发

# 输出示例 2
    SEVERITY: warn
    EVENT: pet_escape
    DESC: 宠物正在用爪子扒拉阳台推拉门，试图从缝隙钻出
    PET_ZONE: 阳台

# 业务边界规则
- pet_stuck (critical): 宠物被卡在狭窄缝隙（如沙发底、柜门夹缝）、被绳索缠绕、被重物压住、在狭窄空间内无法转身或明显痛苦挣扎。
- pet_escape (warn): 宠物正在扒拉门把手、试图钻过窗户栏杆、在阳台边缘徘徊、试图翻越围栏、在门口疯狂抓挠试图外出。
- pet_normal (info): 宠物在地板上正常行走、在猫爬架上休息、在食盆前进食、在开阔区域玩耍、在窝里睡觉。
- no_incident (info): 画面中完全看不到宠物、画面中只有家具或杂物、宠物在画面外。

# 禁止事项
不要输出JSON格式，不要使用markdown代码块（三反引号），不要照抄示例中的文字，只输出SEVERITY、EVENT、DESC及PET_ZONE这四个字段及其对应值，共四行文本。
