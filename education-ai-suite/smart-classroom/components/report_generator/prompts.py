"""
Prompts for the Report Generator.

Contains:
- Template fill prompts (structured JSON output for .docx template filling)
"""

# --- Template Fill Prompts ---
# Used when a .docx template with {placeholder} fields is available.
# The system prompts below are shared by the split-fill generated-field prompts.

TEMPLATE_FILL_SYSTEM_EN = "You are a professional educational analyst. Fill report template fields based on provided data. Output JSON."

TEMPLATE_FILL_SYSTEM_ZH = "你是一个专业的教育分析师。根据提供的数据填充报告模板字段，输出JSON。"


# --- Split-fill: generated-only prompts ---
# Used by the split-fill pipeline. Measured "raw" fields are already filled
# directly from data (passed here as KNOWN FACTS for context); the LLM is asked
# to produce ONLY the descriptive/assessment ("generated") fields.

TEMPLATE_FILL_GENERATED_PROMPT_EN = """You are a classroom evaluation report generator. Some template fields are ALREADY filled from measured data (listed below as Known Facts). Your job is to write ONLY the descriptive/assessment fields listed under "Fields to fill".

## Report Template (for context):
{template_raw_text}

## Known Facts (already-measured values — treat as ground truth, use them but do NOT output them):
{known_facts}

## Collected Classroom Data:
{collected_data}

## Fields to fill (output ONLY these keys):
{fields_json}

## What each field means (assess along these dimensions):
{field_definitions}

## Rules:
- Output ONLY the fields listed above; do NOT include any known-fact field.
- Base every assessment on the collected data and known facts; do NOT invent statistics.
- If data for a field is unavailable, fill with "Data not available"
- Descriptive fields: concise, no more than 2-3 sentences
- recommendations field: separate multiple items with newlines
- Output pure JSON only, no ```json markers or other text

Output JSON:"""

TEMPLATE_FILL_GENERATED_PROMPT_ZH = """你是一个课堂评估报告生成器。部分模板字段已根据测量数据填好（下方"已知数据"），你只需生成"需要填写的字段"中列出的描述型/评估型字段。

## 报告模板结构（供参考）：
{template_raw_text}

## 已知数据（已测量的真实值——作为事实依据使用，但不要输出这些字段）：
{known_facts}

## 收集到的课堂数据：
{collected_data}

## 需要填写的字段（只输出这些 key）：
{fields_json}

## 各字段含义（请从以下维度进行评估）：
{field_definitions}

## 规则：
- 只输出上面列出的字段，不要包含任何已知数据字段
- 所有评估必须基于收集的数据和已知数据，不要编造统计数据
- 如果某个字段的数据不可用，填写"暂无数据"
- 描述型字段用简洁的句子，不超过2-3句话
- recommendations 字段用换行符分隔多条建议
- 输出纯JSON，不要包含```json标记或其他文字

输出JSON："""


# --- Generated-field assessment dimensions ---
# What each generated field should assess, so the LLM produces a consistent,
# well-defined evaluation instead of guessing from the label alone. Keyed by
# field code; only the dimensions for the fields actually being generated this
# run are injected (see build_field_definitions). Custom template placeholders
# not listed here simply contribute no definition line.
GENERATED_FIELD_DEFINITIONS = {
    "interaction_level": {
        "en": "Interaction level — the degree of teacher–student interaction: frequency of teacher questions and student hand-raises, and how much back-and-forth the lesson had. Ground this in the measured question count and hand-raise numbers.",
        "zh": "学生互动水平——师生互动的程度：教师提问频次、学生举手次数，以及课堂一问一答的活跃程度。以已测量的提问次数和举手人次为依据。",
    },
    "classroom_atmosphere": {
        "en": "Classroom atmosphere — the overall learning climate that emerges from the engagement signals (hand-raises, participation, interaction density): e.g. active and engaged, calm and orderly, or quiet/passive. Base this on the engagement statistics, not speculation.",
        "zh": "课堂氛围——从参与信号（举手、参与度、互动密度）综合反映出的整体学习氛围：如积极活跃、平稳有序、或安静被动。以参与度统计为依据，不要臆测。",
    },
    "recommendations": {
        "en": "Recommendations — 2-3 concrete, actionable suggestions for the teacher, each grounded in a specific observation from the data above (e.g. pacing, interaction, content structure). Avoid generic advice.",
        "zh": "改进建议——为教师提供 2-3 条具体、可操作的建议，每条都应基于上述数据中的某个具体观察（如节奏、互动、内容结构），避免空泛的套话。",
    },
}


def build_field_definitions(field_codes, language: str = "en") -> str:
    """Return a bullet list of assessment dimensions for the given field codes.

    Only fields present in GENERATED_FIELD_DEFINITIONS contribute a line; unknown
    codes (custom template placeholders) are silently skipped. Returns a neutral
    marker when none of the fields have a definition.
    """
    lang = "zh" if language == "zh" else "en"
    lines = []
    for code in field_codes:
        entry = GENERATED_FIELD_DEFINITIONS.get(code)
        if entry:
            lines.append(f"- {code}: {entry[lang]}")
    if not lines:
        return "（无特定说明，请根据字段名称和数据合理评估）" if lang == "zh" \
            else "(No specific definitions; assess reasonably from the field name and data.)"
    return "\n".join(lines)
