from components.base_component import PipelineComponent
import openvino_genai as ov_genai
import logging
import re
from utils.config_loader import config
from utils.markdown_cleaner import strip_think_tokens

logger = logging.getLogger(__name__)

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
                    "Topic title rules (IMPORTANT — titles are used for semantic search and embedding):\n"
                    "- Each title must be a descriptive sentence of 10–15 words (or equivalent in Chinese)\n"
                    "- The title must clearly summarize WHAT was taught in that segment\n"
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
                    f"Remember:\n"
                    f"1. Output ONLY a JSON array with 15–25 objects. Count before you output.\n"
                    f"2. Each topic title must be a descriptive 10–15 word sentence useful for semantic search.\n"
                    + (f"3. WRITE ALL TITLES IN SIMPLIFIED CHINESE ONLY. No English at all.\n"
                       if use_zh
                       else "3. Write all titles in English.\n")
                    + f"4. Topic titles are critical—they are embedded and searchable, so make them clear and complete."
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
    def _repair_truncated_array(text: str) -> str | None:
        """Attempt to recover a valid JSON array from truncated LLM output by
        truncating at the last complete object and closing the array."""
        start = text.find("[")
        if start == -1:
            return None
        last_brace = text.rfind("},")
        if last_brace == -1:
            last_brace = text.rfind("}")
        if last_brace == -1:
            return None
        return text[start:last_brace + 1] + "]"

    @staticmethod
    def _sanitize_json(text: str) -> str:
        """Fix corrupted JSON keys (e.g., 'end背景' or 'end_背景' → 'end_time')."""
        # Replace malformed keys with correct ones (matches any chars after the
        # prefix, with or without an underscore, to handle token-corrupted output).
        text = re.sub(r'"end[^"]*"\s*:', '"end_time":', text)
        text = re.sub(r'"start[^"]*"\s*:', '"start_time":', text)
        text = re.sub(r'"topic[^"]*"\s*:', '"topic":', text)
        return text

    @staticmethod
    def _clean_topics_output(raw: str) -> str:
        """
        Clean the raw output from the model to extract a valid JSON array string.
        """
        import json

        def try_parse(s: str):
            try:
                s = ContentSegmentationComponent._sanitize_json(s)
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return s
            except Exception:
                pass
            return None

        text = raw.strip()

        result = try_parse(text)
        if result:
            return result

        stripped = re.sub(r"```[a-zA-Z]*\n?([\s\S]*?)```", r"\1", text).strip()
        result = try_parse(stripped)
        if result:
            return result

        extracted = ContentSegmentationComponent._extract_json_array(stripped)
        if extracted:
            result = try_parse(extracted)
            if result:
                return result

        extracted = ContentSegmentationComponent._extract_json_array(text)
        if extracted:
            result = try_parse(extracted)
            if result:
                return result

        # Strategy 5: repair truncated array by truncating at last complete object
        repaired = ContentSegmentationComponent._repair_truncated_array(text)
        if repaired:
            result = try_parse(repaired)
            if result:
                logger.warning("_clean_topics_output: recovered from truncated LLM output.")
                return result

        logger.error("_clean_topics_output: all strategies failed. Preview: %s", raw[:200])
        raise ValueError("INVALID_TOPICS_FORMAT")

    def generate_topics(self, transcript_text, language=None):
        try:
            logger.info("Generating topic segmentation...")

            prompt = self.model.tokenizer.apply_chat_template(
                self._build_messages(transcript_text, language=language),
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False
            )

            full_output = strip_think_tokens(self.model.generate(prompt, False))
            clean_output = self._clean_topics_output(full_output)
            logger.info("Topic segmentation completed.")
            return clean_output

        except Exception as e:
            logger.error(f"Topic segmentation failed: {e}")
            raise
