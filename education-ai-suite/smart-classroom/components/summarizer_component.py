from components.base_component import PipelineComponent
from components.board_ocr.board_ocr_service import read_board_ocr_with_status
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.prompt_loader import load_prompt
from utils.storage_manager import StorageManager
from utils.session_paths import SessionPaths
from utils import text_chunker
from utils.transcript_parser import parse_transcript_lines
from model_manager import ModelManager
import logging, os
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_MAX_FOLD_ROUNDS = 2


@dataclass
class _SummaryRun:
    """Timings and counters for one summarization, written out when it ends.

    The run has to survive an exception on the way out -- the metrics are the
    only record of a summary that failed halfway -- so the counters live here
    rather than as locals threaded into a ``finally``.
    """

    start: float = field(default_factory=time.perf_counter)
    reduce_start: float = 0.0
    first_token: float = 0.0
    strategy: str = "single_shot"
    chunks: int = 1
    map_time: float = 0.0
    input_tokens: int = -1
    prompt_tokens: int = -1
    output_tokens: int = -1

    def __post_init__(self):
        self.reduce_start = self.start

    def metrics(self, model: str) -> dict:
        end = time.perf_counter()
        elapsed = end - self.start
        # ttft is client-visible, so it counts the map stage too.
        ttft = (self.first_token - self.start) if self.first_token else -1
        reduce_ttft = (self.first_token - self.reduce_start) if self.first_token else -1
        decode = (end - self.first_token) if self.first_token else elapsed
        tps = ((self.output_tokens - 1) / decode
               if decode > 0 and self.output_tokens > 1 else -1)
        return {
            "configuration.summarizer_model": model,
            "performance.summarizer_time": round(elapsed, 4),
            "performance.ttft": f"{round(ttft, 4)}s",
            "performance.tps": round(tps, 4),
            "performance.total_tokens": self.output_tokens,
            "performance.summarization_time": f"{round(elapsed, 4)}s",
            "performance.summary_strategy": self.strategy,
            "performance.summary_chunks": self.chunks,
            "performance.summary_map_time": f"{round(self.map_time, 4)}s",
            "performance.summary_input_tokens": self.input_tokens,
            "performance.summary_prompt_tokens": self.prompt_tokens,
            "performance.reduce_ttft": f"{round(reduce_ttft, 4)}s",
        }

# The mm:ss-mm:ss span in a note's own header, read back when folding notes.
_SPAN_RE = re.compile(r"^\[(?:SEGMENT|NOTES)[^\]]*\]\s*(\d\d:\d\d)-(\d\d:\d\d)", re.M)

# Focus instructions for different modes
_MAP_FOCUS_PROMPTS = {
    "en": {
        "teacher": "Record only the teacher's explanations; ignore student dialog.",
        "hybrid": "Teacher explanations are primary; include student questions only as context.",
        "dialog": "Cover both teacher explanations and student dialog.",
    },
    "zh": {
        "teacher": "只记录教师的讲解，完全忽略学生对话。",
        "hybrid": "以教师讲解为主，学生提问仅在有助于理解上下文时记录。",
        "dialog": "教师讲解和学生对话都要记录。",
    },
}

class SummarizerComponent(PipelineComponent):
    _model = None
    _config = None

    def __init__(self, session_id, mode="dialog"):
        self.session_id = session_id
        self.mode = mode.lower()
        self.board_ocr_partial = False
        
        text_gen = config.models.text_gen
        SummarizerComponent._model = ModelManager.instance().text_gen()
        SummarizerComponent._config = ("vlm", text_gen.vlm_name, text_gen.device)

        self.summarizer = SummarizerComponent._model
        self.model_name = text_gen.vlm_name
        self.provider = text_gen.provider

    # ---------------- SYSTEM PROMPT SELECTOR ----------------

    def _get_system_prompt(self, has_board=False):
        lang = config.app.language
        mode_name = self.mode if self.mode in ("teacher", "hybrid") else "dialog"
        prompt = load_prompt("summarizer", lang, mode_name)

        if has_board:
            addendum = load_prompt("summarizer", lang, "board_ocr_addendum")
            prompt = f"{prompt}\n\n{addendum}"

        return prompt

    # ---------------- INPUT SELECTOR ----------------

    def _load_input_text(self):
        if self.mode == "teacher":
            path = str(SessionPaths.teacher_transcript_path(self.session_id))
        else:
            path = str(SessionPaths.transcript_path(self.session_id))

        return StorageManager.read_text_file(path)

    def _load_board_ocr_text(self):
        try:
            text, status = read_board_ocr_with_status(self.session_id)
        except Exception as e:
            logger.warning(f"Could not load board OCR text: {e}")
            return ""
        self.board_ocr_partial = bool(text) and status not in ("done", "not_started")
        if self.board_ocr_partial:
            logger.warning(
                f"Board OCR still {status} for session {self.session_id}; the summary's "
                f"board content may be incomplete."
            )
        return text

    # ---------------- MESSAGE BUILDER ----------------

    def _get_message(self, input_text, board_text=""):
        system_prompt = self._get_system_prompt(has_board=bool(board_text))
        logger.debug(f"Summarizer mode: {self.mode}")
        logger.debug(f"System Prompt Loaded")

        if board_text:
            body = (
                "[TRANSCRIPT]\n"
                f"{input_text}\n\n"
                "[BOARD CONTENT]\n"
                f"{board_text}"
            )
        else:
            body = input_text

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": body}
        ]

    def _missing_sections(self, summary_text, has_board=False):
        """Return the sections the system prompt asks for but the summary lacks."""
        heading = re.compile(r"^##\s+(.+?)\s*$", re.M)
        expected = heading.findall(self._get_system_prompt(has_board=has_board))
        produced = set(heading.findall(summary_text))
        return [s for s in expected if s not in produced]

    # ---------------- LONG-TRANSCRIPT SEGMENTATION ----------------

    def _chunking_config(self):
        return getattr(getattr(config.models, "text_gen", None), "chunking", None)

    def _tokenizer(self):
        try:
            return self.summarizer.tokenizer
        except Exception:  # noqa: BLE001
            logger.debug("text_gen tokenizer unavailable; using the estimator.", exc_info=True)
            return None

    def _prompt_budget(self):
        return text_chunker.budget_from_config(
            self._chunking_config(),
            getattr(config.models.text_gen, "device", "GPU"),
        )

    def _stage_reserve(self):
        """Return what one *map* call spends on everything but the transcript.

        A map call is cheaper than the whole-lesson one that ``_call_overhead``
        sizes: a short prompt, a short note, and no board text. Measuring this
        component's own prompts keeps a segment as large as this component can
        actually afford.
        """
        prompt = text_chunker.count_tokens(
            load_prompt("summarizer", config.app.language, "map"), self._tokenizer()
        )
        return prompt + int(
            getattr(self._chunking_config(), "map_max_new_tokens", 1536)
        )

    def _plan_chunks(self, input_text, board_text):
        """Return ``(chunks, budget, reserve, total)``; no chunks means one call does.

        Planned over the transcript this component will actually send. Sharing
        one plan with the segmentation used to look tidier, but it measured that
        component's timestamped copy -- a different token count, against a
        different reserve -- so the shared answer fitted neither caller.
        """
        tokenizer = self._tokenizer()
        device = getattr(config.models.text_gen, "device", "GPU")
        budget = self._prompt_budget()
        reserve = self._call_overhead(board_text)

        lines = [l for l in input_text.splitlines() if l and l.strip()]
        total = sum(text_chunker.count_tokens(l, tokenizer) + 1 for l in lines)
        if total <= text_chunker.usable_tokens(budget, reserve):
            text_chunker.warn_if_short_of_memory(
                total + reserve, device, what="summary call"
            )
            return [], budget, reserve, total

        stage_reserve = self._stage_reserve()
        # ``teacher`` mode reads a transcript that carries its own timestamps, so
        # its segments can be labelled with the minutes they cover. The speaker
        # transcript has none, and a segment index is all the map prompt needs.
        parsed = parse_transcript_lines(input_text)
        if parsed:
            chunks = text_chunker.chunk_transcript_lines(
                parsed,
                budget_tokens=budget,
                tokenizer=tokenizer,
                reserve_tokens=reserve,
                stage_reserve_tokens=stage_reserve,
                label="segment",
            )
        else:
            chunks = text_chunker.chunk_lines(
                lines,
                budget_tokens=budget,
                tokenizer=tokenizer,
                reserve_tokens=reserve,
                stage_reserve_tokens=stage_reserve,
                label="segment",
            )

        # The reduce call carries the notes rather than the transcript, so the
        # largest map call is the peak this session asks for.
        text_chunker.warn_if_short_of_memory(
            max(c.tokens for c in chunks) + stage_reserve, device,
            what="largest summary segment",
        )
        return chunks, budget, reserve, total

    def _call_overhead(self, board_text=""):
        """Return what the *whole-lesson* call spends on everything but transcript.

        Sizes the single-call and reduce prompts. A chunk is cheaper -- short
        prompt, short answer, no board text -- and is sized by
        ``_stage_reserve`` instead.
        """
        tokenizer = self._tokenizer()
        overhead = text_chunker.count_tokens(
            self._get_system_prompt(has_board=bool(board_text)), tokenizer
        )
        if board_text:
            overhead += text_chunker.count_tokens(board_text, tokenizer)
        return overhead + int(
            getattr(config.models.text_gen, "max_new_tokens", 5120)
        )

    @staticmethod
    def _segment_header(chunk):
        """Label one segment, with its minutes when the chunk carries times."""
        label = f"[SEGMENT {chunk.index + 1}/{chunk.total}]"
        if chunk.start is None or chunk.end is None:
            return label
        mmss = lambda s: f"{int(s) // 60:02d}:{int(s) % 60:02d}"  # noqa: E731
        return f"{label} {mmss(chunk.start)}-{mmss(chunk.end)}"

    @staticmethod
    def _fold_header(group):
        """Label a group of notes by the span of the segments it absorbs.

        A fold rewrites its input, so the headers inside the group do not
        survive it. Lifting the outer span out first is what keeps the reduce
        stage able to order what it is given.
        """
        spans = _SPAN_RE.findall(group.text)
        label = f"[NOTES {group.index + 1}/{group.total}]"
        return f"{label} {spans[0][0]}-{spans[-1][1]}" if spans else label

    def _map_messages(self, chunk, header=None):
        lang = config.app.language
        mode_name = self.mode if self.mode in ("teacher", "hybrid") else "dialog"
        system = load_prompt("summarizer", lang, "map")
        focus = _MAP_FOCUS_PROMPTS.get(lang, _MAP_FOCUS_PROMPTS["en"])[mode_name]
        header = header or self._segment_header(chunk)
        return [
            {"role": "system", "content": system.replace("{focus}", focus)},
            {"role": "user", "content": f"{header}\n\n{chunk.text}"},
        ]

    def _generate_note(self, chunk, max_new_tokens, header=None):
        """Generate terse notes for a single segment, or for a group of notes."""
        header = header or self._segment_header(chunk)
        raw = self.summarizer.generate(
            # The prompt and the answer must carry the same label, or a fold
            # tells the model it is reading segment 1 of 3 of the lesson.
            messages=self._map_messages(chunk, header),
            stream=False,
            max_new_tokens=max_new_tokens,
            enable_thinking=False,
        )
        note = str(raw).strip()
        return f"{header}\n{note}" if note else ""

    def _fold_notes(self, notes, budget, max_new_tokens, reserve):
        """Re-summarize notes that together exceed the reduce budget.

        A generator: it reports progress per note group and returns the folded
        notes, so the caller drives it with ``yield from``. Folding can run
        several model calls, and without these events the client would sit on
        the last map segment for the whole stage.
        """
        tokenizer = self._tokenizer()
        stage_reserve = self._stage_reserve()
        # The notes become the reduce prompt, and reduce writes the summary.
        reduce_budget = text_chunker.usable_tokens(budget, reserve)
        for round_no in range(_MAX_FOLD_ROUNDS):
            size = text_chunker.count_tokens("\n\n".join(notes), tokenizer)
            if size <= reduce_budget:
                return notes
            logger.info("Notes exceed the reduce budget; folding (round %d).", round_no + 1)
            groups = text_chunker.chunk_lines(
                notes, budget_tokens=budget,
                overlap_lines=0, tokenizer=tokenizer,
                reserve_tokens=reserve, stage_reserve_tokens=stage_reserve,
                label="note group",
            )
            # These headers number note groups, not lesson segments, so they
            # must not reuse the [SEGMENT n/m] labels the notes already carry.
            folded = []
            for group in groups:
                # Announced one group at a time, on the same rule as the map
                # loop: the event has to precede the call it describes.
                yield {"event": "progress", "stage": "fold",
                       "chunk": group.index + 1, "chunks": group.total,
                       "round": round_no + 1}
                note = self._generate_note(
                    group, max_new_tokens, header=self._fold_header(group)
                )
                if note:
                    folded.append(note)
            notes = folded

        size = text_chunker.count_tokens("\n\n".join(notes), tokenizer)
        if size > reduce_budget:
            logger.warning(
                "Notes still hold %d tokens against a %d-token reduce budget after "
                "%d fold round(s); the reduce prompt will be over budget and the "
                "summary may be truncated.", size, reduce_budget, _MAX_FOLD_ROUNDS,
            )
        return notes

    def _reduce_input(self, notes):
        instruction = load_prompt("summarizer", config.app.language, "reduce_instruction")
        return f"{instruction.strip()}\n\n" + "\n\n".join(notes)

    # ---------------- MAIN PROCESS ----------------

    def process(self, _):

        input_text = self._load_input_text()
        board_text = self._load_board_ocr_text()
        if board_text:
            logger.info("Board OCR for session %s (%d chars); including in summary.",
                        self.session_id, len(board_text))

        summary_path = str(SessionPaths.summary_path(self.session_id))
        StorageManager.save(summary_path, "", append=False)

        run = _SummaryRun()
        raw_tokens = []

        try:
            chunks, budget, reserve = [], 0, 0
            cfg = self._chunking_config()
            if cfg is not None and bool(getattr(cfg, "enabled", True)):
                # input_tokens is the transcript as read; summing the chunks
                # would count the overlap lines twice.
                chunks, budget, reserve, run.input_tokens = self._plan_chunks(
                    input_text, board_text
                )

            if len(chunks) > 1:
                run.strategy = "map_reduce"
                run.chunks = len(chunks)
                map_start = time.perf_counter()
                max_new = int(getattr(cfg, "map_max_new_tokens", 1536))
                notes = []
                for chunk in chunks:
                    # Emitted before each segment, not all up front: this is
                    # what the client renders as "analysing part 3 of 7".
                    yield {"event": "progress", "stage": "map",
                           "chunk": chunk.index + 1, "chunks": chunk.total}
                    note = self._generate_note(chunk, max_new)
                    if note:
                        notes.append(note)
                notes = yield from self._fold_notes(notes, budget, max_new, reserve)
                run.map_time = time.perf_counter() - map_start
                yield {"event": "progress", "stage": "reduce",
                       "chunk": run.chunks, "chunks": run.chunks}
                body = self._reduce_input(notes)
            else:
                body = input_text

            messages = self._get_message(body, board_text)
            run.prompt_tokens = text_chunker.count_tokens(
                "".join(m["content"] for m in messages), self._tokenizer()
            )
            logger.info(
                "Summarizing session %s: strategy=%s chunks=%d prompt=%d tokens",
                self.session_id, run.strategy, run.chunks, run.prompt_tokens,
            )

            run.reduce_start = time.perf_counter()
            # Reasoning is already filtered out of the stream by generate().
            for token in self.summarizer.generate(messages=messages, enable_thinking=False):
                if not run.first_token:
                    run.first_token = time.perf_counter()
                raw_tokens.append(token)
                StorageManager.save_async(summary_path, token, append=True)
                yield token

        finally:
            raw_text = "".join(raw_tokens)
            run.output_tokens = self._count_output(raw_text)
            self._warn_about_missing_sections(raw_text, board_text, run.strategy)
            StorageManager.update_csv(
                path=str(SessionPaths.metrics_path(self.session_id)),
                new_data=run.metrics(f"{self.provider}/{self.model_name}"),
            )

    def _count_output(self, raw_text):
        try:
            return len(self.summarizer.tokenizer.encode(raw_text)) if raw_text else 0
        except Exception:  # noqa: BLE001
            return -1

    def _warn_about_missing_sections(self, raw_text, board_text, strategy):
        missing = self._missing_sections(raw_text, has_board=bool(board_text)) if raw_text else []
        if missing:
            logger.warning(
                "Summary for %s (%s) is missing section(s): %s. Downstream "
                "report fields sourced from them will be empty.",
                self.session_id, strategy, ", ".join(missing),
            )
