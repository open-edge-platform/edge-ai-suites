from components.base_component import PipelineComponent
import json
import logging
import re
import json_repair
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from utils.config_loader import config
from utils.prompt_loader import load_prompt
from utils import text_chunker
from utils.transcript_parser import parse_transcript_lines
from components.segmentation import topic_merge

logger = logging.getLogger(__name__)

MIN_TOPICS = 15
MAX_TOPICS = 25

# CAUTION: "rule" and "output" open with the list numbers they occupy in
# user.txt (5. and 3.). Renumbering that file means renumbering these.

_LANGUAGE_PARTS = {
    "en": {
        "instruction": "All topic titles must be written in English.",
        "rule": "5. Write all titles in English.",
        "example": "- Example in English: 'Explaining how Newton's third law "
                   "applies to rocket propulsion with examples'",
    },
    "zh": {
        "instruction": "CRITICAL: All topic titles MUST be written in Simplified "
                       "Chinese (简体中文). Do NOT output English. Each title must "
                       "be a complete sentence in Chinese describing the teaching "
                       "content.",
        "rule": "5. WRITE ALL TITLES IN SIMPLIFIED CHINESE ONLY. No English at all.",
        "example": "- LANGUAGE: Write ONLY in Simplified Chinese. Example: "
                   "'解释牛顿第三定律如何应用于火箭推进及示例'",
    },
}

_MODE_PARTS = {
    "whole": {
        "count": "HARD CONSTRAINT: Output EXACTLY between {min_topics} and "
                 "{max_topics} topic objects. NEVER more than {max_topics}. "
                 "NEVER fewer than {min_topics}.\n"
                 "\n"
                 "BEFORE outputting, count your segments. If count > {max_topics}, "
                 "merge the most related adjacent segments until count ≤ {max_topics}.",
        "request": "Segment this transcript into {min_topics}–{max_topics} topics "
                   "(MAXIMUM {max_topics}, merge aggressively if needed).",
        "output": "3. Output ONLY a JSON array with {min_topics}–{max_topics} "
                  "objects. Count before you output.",
    },
    "window": {
        "count": "HARD CONSTRAINT: Output EXACTLY {quota} topic object(s). "
                 "Not more, not fewer.\n"
                 "\n"
                 "You are looking at ONE WINDOW of a longer lesson, covering "
                 "{window_start}s to {window_end}s. Every start_time and end_time "
                 "you output MUST fall inside that range.",
        "request": "Segment this transcript window into EXACTLY {quota} topic(s).",
        "output": "3. Output ONLY a JSON array with EXACTLY {quota} object(s), "
                  "all timestamps between {window_start} and {window_end}.",
    },
}


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

    def _build_messages(self, transcript_text, language=None, *, quota=None,
                        window_start=None, window_end=None):
        """Build a whole-transcript or window prompt from shared templates."""
        lang = (language or getattr(config.app, "language", "en") or "en").lower()
        lang = "zh" if lang.startswith("zh") else "en"
        mode = "window" if quota is not None else "whole"
        fields = {
            "{min_topics}": str(MIN_TOPICS),
            "{max_topics}": str(MAX_TOPICS),
            "{quota}": str(quota),
            "{window_start}": "" if quota is None else f"{window_start:.0f}",
            "{window_end}": "" if quota is None else f"{window_end:.0f}",
        }

        def fill(text):
            # .replace, not .format: the templates hold literal JSON braces.
            for key, value in fields.items():
                text = text.replace(key, value)
            return text

        def part(name):
            return fill(load_prompt("segmentation", name))

        lang_parts = _LANGUAGE_PARTS[lang]
        mode_parts = _MODE_PARTS[mode]

        system = (part("system")
                  .replace("{language_instruction}", fill(lang_parts["instruction"]))
                  .replace("{count_constraint}", fill(mode_parts["count"]))
                  .replace("{language_example}", fill(lang_parts["example"])))
        user = (part("user")
                .replace("{request}", fill(mode_parts["request"]))
                .replace("{output_constraint}", fill(mode_parts["output"]))
                .replace("{language_rule}", fill(lang_parts["rule"]))
                .replace("{transcript}", transcript_text))
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
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

    def _generate(self, messages: list, max_new_tokens: int | None = None) -> str:
        try:
            return self.model.generate(
                messages=messages,
                stream=False,
                enable_thinking=False,
                max_new_tokens=max_new_tokens,
                json_schema=_topics_json_schema(),
            )
        except TypeError:
            logger.info("Backend does not accept json_schema; generating unconstrained.")
        except Exception as exc:
            logger.warning(
                "Constrained generation failed (%s); retrying unconstrained.", exc
            )
        return self.model.generate(
            messages=messages, stream=False, enable_thinking=False,
            max_new_tokens=max_new_tokens,
        )

    # ---------------- WINDOWED SEGMENTATION ----------------

    def _seg_config(self):
        return getattr(getattr(config.models, "text_gen", None), "segmentation", None)

    def _tokenizer(self):
        try:
            return self.model.tokenizer
        except Exception:  # noqa: BLE001
            logger.debug("text_gen tokenizer unavailable; using the estimator.", exc_info=True)
            return None

    def _chunking_config(self):
        return getattr(getattr(config.models, "text_gen", None), "chunking", None)

    def _prompt_budget(self):
        return text_chunker.budget_from_config(
            self._chunking_config(),
            getattr(config.models.text_gen, "device", "GPU"),
        )

    def _stage_reserve(self):
        """Return what one *window* call spends on everything but the transcript.

        A window call sends both templates and writes a shorter answer than the
        whole-lesson call ``_call_overhead`` sizes. Measuring this component's
        own prompts keeps a window as large as this component can afford.
        """
        tokenizer = self._tokenizer()
        prompt = (text_chunker.count_tokens(load_prompt("segmentation", "system"), tokenizer)
                  + text_chunker.count_tokens(load_prompt("segmentation", "user"), tokenizer))
        return prompt + int(
            getattr(self._seg_config(), "window_max_new_tokens", 1024)
        )

    def _plan_windows(self, transcript_text, language=None):
        """Return the transcript windows, or [] to segment in a single call.

        Planned over this component's own transcript. Sharing one plan with the
        summary used to look tidier, but the two send different renderings of the
        lesson against different reserves, so one answer fitted neither.
        """
        cfg = self._chunking_config()
        if cfg is None or not bool(getattr(cfg, "enabled", True)):
            return []

        lines = parse_transcript_lines(transcript_text)
        if not lines:
            logger.info("Transcript carries no timestamps; segmenting in one call.")
            return []

        tokenizer = self._tokenizer()
        device = getattr(config.models.text_gen, "device", "GPU")
        budget = self._prompt_budget()
        reserve = self._call_overhead(language)

        total = sum(text_chunker.count_tokens(l, tokenizer) + 1
                    for l in text_chunker.render_transcript_lines(lines))
        if total <= text_chunker.usable_tokens(budget, reserve):
            text_chunker.warn_if_short_of_memory(
                total + reserve, device, what="segmentation call"
            )
            return []

        stage_reserve = self._stage_reserve()
        windows = text_chunker.chunk_transcript_lines(
            lines,
            budget_tokens=budget,
            tokenizer=tokenizer,
            reserve_tokens=reserve,
            stage_reserve_tokens=stage_reserve,
            label="window",
        )

        if len(windows) < 2:
            # Unreachable: the text is already past what one call holds. A lone
            # window under a per-window quota is worse than the single-call
            # prompt, so fall back rather than trust it.
            logger.warning("Windowing produced %d window(s); segmenting in one call.",
                           len(windows))
            return []

        text_chunker.warn_if_short_of_memory(
            max(w.tokens for w in windows) + stage_reserve, device,
            what="largest segmentation window",
        )
        return windows

    def _call_overhead(self, language=None):
        """Return the tokens the single call spends on the template and answer.

        Rendering the prompt around an empty transcript measures the
        instructions exactly, which beats guessing at them with a ratio. This
        sizes the whole-lesson call; a window's own overhead is smaller and
        lives in ``_stage_reserve``.
        """
        try:
            template = "".join(
                m["content"] for m in self._build_messages("", language=language)
            )
            overhead = text_chunker.count_tokens(template, self._tokenizer())
        except Exception:  # noqa: BLE001
            logger.debug("Could not measure the segmentation prompt.", exc_info=True)
            overhead = 0
        return overhead + int(
            getattr(config.models.text_gen, "max_new_tokens", 5120)
        )

    def _generate_window(self, window, quota, language, max_new_tokens):
        """Segment one window and return its normalized topics; [] on failure."""
        messages = self._build_messages(
            window.text, language=language, quota=quota,
            window_start=window.start, window_end=window.end,
        )
        try:
            raw = self._generate(messages, max_new_tokens=max_new_tokens)
            topics = json.loads(self._clean_topics_output(raw))
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Window %d/%d (%.0fs-%.0fs) failed to segment: %s",
                window.index + 1, window.total, window.start, window.end, e,
            )
            return []
        return topic_merge.normalize_topics(
            topics, window_start=window.start, window_end=window.end
        )

    def generate_topics(self, transcript_text, language=None):
        try:
            logger.info("Generating topic segmentation...")

            windows = self._plan_windows(transcript_text, language)
            if windows:
                return self._generate_topics_windowed(windows, language)

            full_output = self._generate(
                self._build_messages(transcript_text, language=language)
            )
            clean_output = self._clean_topics_output(full_output)
            logger.info("Topic segmentation completed.")
            return clean_output

        except Exception as e:
            logger.error(f"Topic segmentation failed: {e}")
            raise

    def _generate_topics_windowed(self, windows, language):
        """Segment each window under its topic quota, then merge the results."""
        seg = self._seg_config()
        target = int(getattr(seg, "topics_target", 20))
        min_count = int(getattr(seg, "topics_min", 15))
        max_count = int(getattr(seg, "topics_max", 25))
        max_new_tokens = int(getattr(seg, "window_max_new_tokens", 1024))

        quotas = topic_merge.allocate_quota([w.tokens for w in windows], target)
        logger.info(
            "Segmenting %d windows (quotas %s) toward %d topics.",
            len(windows), quotas, target,
        )

        collected = []
        for window, quota in zip(windows, quotas):
            collected.extend(
                self._generate_window(window, quota, language, max_new_tokens)
            )

        if not collected:
            raise ValueError("INVALID_TOPICS_FORMAT")

        merged = topic_merge.merge_topics(
            collected, min_count=min_count, max_count=max_count
        )
        logger.info(
            "Topic segmentation completed: %d raw topics from %d windows -> %d merged.",
            len(collected), len(windows), len(merged),
        )
        return json.dumps(merged, ensure_ascii=False)
