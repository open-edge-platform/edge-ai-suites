from components.base_component import PipelineComponent
import openvino_genai as ov_genai
import json
import logging
import re
import json_repair
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from utils.config_loader import config

logger = logging.getLogger(__name__)

MIN_TOPICS = 15
MAX_TOPICS = 25


class Topic(BaseModel):
    """One segmentation topic. Backs both the decoding grammar and output validation."""
    model_config = ConfigDict(extra="ignore")

    topic: str = Field(min_length=1)
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)


def _topics_json_schema() -> str:
    """Schema for the topic array, passed to the decoder as a grammar."""
    item = Topic.model_json_schema()
    # Restrict generation to the three declared keys.
    item["additionalProperties"] = False
    return json.dumps({
        "type": "array",
        "items": item,
        "minItems": MIN_TOPICS,
        "maxItems": MAX_TOPICS,
    })


class ContentSegmentationComponent(PipelineComponent):
    def __init__(self, session_id, temperature=0.2):
        self.session_id = session_id
        self.temperature = temperature

    def _build_messages(self, transcript_text, language=None):
        lang = (language or getattr(config.app, "language", "en") or "en").lower()
        use_zh = lang.startswith("zh")
        lang_instruction = (
            "CRITICAL: All topic titles MUST be written in Simplified Chinese (简体中文). Do NOT output English. Each title must be a complete sentence in Chinese describing the teaching content."
            if use_zh
            else "All topic titles must be written in English."
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are a transcript segmentation engine. Your ONLY job is to output valid JSON.\n\n"
                    f"{lang_instruction}\n\n"
                    "HARD CONSTRAINT: Output EXACTLY between 15 and 25 topic objects. NEVER more than 25. NEVER fewer than 15.\n\n"
                    "BEFORE outputting, count your segments. If count > 25, merge the most related adjacent segments until count ≤ 25.\n\n"
                    "Segmentation rules:\n"
                    "- Each topic = one major teaching concept (think: lesson chapters, not paragraphs)\n"
                    "- Each topic must span multiple minutes\n"
                    "- Ignore minor explanation shifts or small tangents\n"
                    "- Merge adjacent related segments aggressively\n"
                    "- Do NOT split mid-sentence\n"
                    "- Use only timestamps present in the transcript\n\n"
                    "CRITICAL ALIGNMENT RULE:\n"
                    "- BEFORE assigning a topic title to a time range, READ the actual text within [start_time-end_time]\n"
                    "- The topic title MUST describe what is ACTUALLY said in that time range\n"
                    "- Do NOT predict what 'should' be discussed — describe what IS discussed\n"
                    "- VERIFY: Does your topic title match the actual words spoken in that segment?\n\n"
                    "Topic title rules (IMPORTANT — titles are used for semantic search and embedding):\n"
                    "- Each title must be a descriptive sentence of 10–15 words (or equivalent in Chinese)\n"
                    "- The title must clearly summarize WHAT was taught in that segment\n"
                    "- Base the title ONLY on the actual content within the timestamp range\n"
                    "- Write as if describing the segment to someone who hasn't seen the transcript\n"
                    + ("- LANGUAGE: Write ONLY in Simplified Chinese. Example: '解释牛顿第三定律如何应用于火箭推进及示例'\n"
                       if use_zh
                       else "- Example in English: 'Explaining how Newton's third law applies to rocket propulsion with examples'\n")
                    + "- Bad: 'Newton law', 'Topic 3', 'Continued explanation'\n\n"
                    "Output format — return ONLY this JSON, nothing else:\n"
                    "[{\"topic\": \"<descriptive title>\", \"start_time\": <float>, \"end_time\": <float>}]\n\n"
                    "No markdown. No explanation. No comments. No text outside the JSON array."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Segment this transcript into 15–25 topics (MAXIMUM 25, merge aggressively if needed).\n\n"
                    f"{transcript_text}\n\n"
                    f"CRITICAL INSTRUCTIONS:\n"
                    f"1. READ the actual text at each timestamp range BEFORE writing the topic title\n"
                    f"2. Topic titles must describe what IS said, not what you think should be said\n"
                    f"3. Output ONLY a JSON array with 15–25 objects. Count before you output.\n"
                    f"4. Each topic title must be a descriptive 10–15 word sentence useful for semantic search.\n"
                    + (f"5. WRITE ALL TITLES IN SIMPLIFIED CHINESE ONLY. No English at all.\n"
                       if use_zh
                       else "5. Write all titles in English.\n")
                    + f"6. Topic titles are critical—they are embedded and searchable, so make them clear and complete.\n"
                    f"7. VERIFY: For each topic, check that the title matches the actual content in that time range."
                )
            }
        ]

    @staticmethod
    def _extract_json_array(text: str) -> str | None:
        """Extract the first balanced [...] block from a string."""
        start = text.find("[")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    @staticmethod
    def _sanitize_json(text: str) -> str:
        """Restore corrupted keys ('end背景') and separators ('"end_time">2.0')."""
        for prefix, canonical in (("end", "end_time"), ("start", "start_time"), ("topic", "topic")):
            # Key name corrupted mid-token, separator mistyped, or both.
            text = re.sub(rf'"{prefix}[^"]*"\s*[:>=;：＝]\s*', f'"{canonical}": ', text)
            # Separator missing: a string value is never followed directly by a
            # string or a number, so only a key can match here.
            text = re.sub(rf'"{prefix}[^"]*"(?=\s*["\d-])', f'"{canonical}":', text)
        # Trailing commas before a closing bracket.
        text = re.sub(r',\s*([\]}])', r'\1', text)
        return text

    @staticmethod
    def _validate_topics(objs: list) -> str | None:
        """Drop entries that fail the Topic schema, sort by time, and dump the rest.

        Returns None when nothing survives, which sends the caller to the next
        recovery step.
        """
        kept, dropped = [], 0
        for obj in objs:
            if not isinstance(obj, dict):
                dropped += 1
                continue
            try:
                topic = Topic.model_validate(obj)
            except ValidationError:
                dropped += 1
                continue
            if topic.end_time <= topic.start_time:
                dropped += 1
                continue
            kept.append(topic)

        if not kept:
            return None
        if dropped:
            logger.warning("Topic validation: kept %d, dropped %d invalid.", len(kept), dropped)

        kept.sort(key=lambda t: t.start_time)
        if not MIN_TOPICS <= len(kept) <= MAX_TOPICS:
            logger.warning(
                "Topic count %d is outside the requested %d-%d range.",
                len(kept), MIN_TOPICS, MAX_TOPICS
            )
        return json.dumps([t.model_dump() for t in kept], ensure_ascii=False)

    @staticmethod
    def _parse_topics(text: str, tolerant: bool) -> str | None:
        """Run one sanitize → parse → validate pass.

        ``tolerant`` selects json_repair, which absorbs fences, surrounding
        prose, truncation, single quotes, unescaped inner quotes and missing
        punctuation.
        """
        text = ContentSegmentationComponent._sanitize_json(text)
        try:
            parsed = json_repair.loads(text) if tolerant else json.loads(text)
        except Exception:
            return None
        # json_repair returns "" rather than raising on unrecoverable input.
        if not isinstance(parsed, list):
            return None
        return ContentSegmentationComponent._validate_topics(parsed)

    @staticmethod
    def _clean_topics_output(raw: str) -> str:
        """
        Clean the raw output from the model to extract a valid JSON array string.

        Escalating recovery: strict parse, fence-stripped parse, tolerant parse,
        tolerant parse of the extracted array. Raises when none of them yields a
        topic that passes validation.
        """
        text = raw.strip()

        result = ContentSegmentationComponent._parse_topics(text, tolerant=False)
        if result:
            return result

        # Fenced output is common enough to stay on the quiet path.
        stripped = re.sub(r"```[a-zA-Z]*\n?([\s\S]*?)```", r"\1", text).strip()
        if stripped != text:
            result = ContentSegmentationComponent._parse_topics(stripped, tolerant=False)
            if result:
                return result

        result = ContentSegmentationComponent._parse_topics(text, tolerant=True)
        if result:
            logger.warning("_clean_topics_output: recovered malformed JSON via json_repair.")
            return result

        # Prose containing braces can derail the tolerant parser; retry on just
        # the first balanced [...] block.
        extracted = ContentSegmentationComponent._extract_json_array(text)
        if extracted:
            result = ContentSegmentationComponent._parse_topics(extracted, tolerant=True)
            if result:
                logger.warning("_clean_topics_output: recovered array from surrounding text.")
                return result

        logger.error("_clean_topics_output: all strategies failed. Preview: %s", raw[:200])
        raise ValueError("INVALID_TOPICS_FORMAT")

    def _generate(self, messages: list) -> str:
        try:
            return self.model.generate(
                messages=messages,
                stream=False,
                enable_thinking=False,
                json_schema=_topics_json_schema(),
            )
        except TypeError:
            logger.info("Backend does not accept json_schema; generating unconstrained.")
        except Exception as exc:
            logger.warning(
                "Constrained generation failed (%s); retrying unconstrained.", exc
            )
        return self.model.generate(
            messages=messages, stream=False, enable_thinking=False
        )

    def generate_topics(self, transcript_text, language=None):
        try:
            logger.info("Generating topic segmentation...")

            full_output = self._generate(
                self._build_messages(transcript_text, language=language)
            )
            clean_output = self._clean_topics_output(full_output)
            logger.info("Topic segmentation completed.")
            return clean_output

        except Exception as e:
            logger.error(f"Topic segmentation failed: {e}")
            raise
