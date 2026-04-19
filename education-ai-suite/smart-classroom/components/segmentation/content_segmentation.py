from components.base_component import PipelineComponent
import openvino_genai as ov_genai
import logging
import re
from utils.config_loader import config

logger = logging.getLogger(__name__)

class ContentSegmentationComponent(PipelineComponent):
    def __init__(self, session_id, temperature=0.2):
        self.session_id = session_id
        self.temperature = temperature

    def _build_messages(self, transcript_text):
        return [
            {
                "role": "system",
                "content": (
                    "You are a transcript segmentation engine. Your ONLY job is to output valid JSON.\n\n"
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
                    "- Each title must be a descriptive sentence of 10–15 words\n"
                    "- The title must clearly summarize WHAT was taught in that segment\n"
                    "- Write as if describing the segment to someone who hasn't seen the transcript\n"
                    "- Good: 'Explaining how Newton's third law applies to rocket propulsion with examples'\n"
                    "- Bad: 'Newton law', 'Topic 3', 'Continued explanation'\n\n"
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
                    f"2. Each topic title must be a descriptive 10–15 word sentence useful for semantic search."
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
    def _clean_topics_output(raw: str) -> str:
        """
        Clean the raw output from the model to extract a valid JSON array string.
        """
        import json

        def try_parse(s: str):
            try:
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

        logger.error("_clean_topics_output: all strategies failed. Preview: %s", raw[:200])
        raise ValueError("INVALID_TOPICS_FORMAT")

    def generate_topics(self, transcript_text):
        try:
            logger.info("Generating topic segmentation...")

            prompt = self.model.tokenizer.apply_chat_template(
                self._build_messages(transcript_text),
                tokenize=False,
                add_generation_prompt=True
            )

            full_output = self.model.generate(prompt, False)
            clean_output = self._clean_topics_output(full_output)
            logger.info("Topic segmentation completed.")
            return clean_output

        except Exception as e:
            logger.error(f"Topic segmentation failed: {e}")
            raise
