from components.base_component import PipelineComponent
from components.board_ocr.board_ocr_service import read_board_ocr_with_status
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.artifacts.path import get_artifact_path
from utils.markdown_cleaner import StreamThinkFilter
from utils.model_family import is_qwen3_dense
from utils.prompt_budget import render_summarizer_prompt
from model_manager import ModelManager
import logging, os
import time

logger = logging.getLogger(__name__)

class SummarizerComponent(PipelineComponent):
    _model = None
    _config = None

    def __init__(self, session_id, provider, model_name, device, temperature=0.7, mode="dialog"):
        self.session_id = session_id
        self.mode = mode.lower()
        self.temperature = temperature
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
        prompts = vars(config.models.summarizer.system_prompt)[lang]

        if self.mode == "teacher":
            prompt = prompts.Teacher
        elif self.mode == "hybrid":
            prompt = prompts.Hybrid
        else:
            prompt = prompts.Dialog

        if has_board:
            addendum = vars(config.models.summarizer.board_ocr_prompt)[lang]
            prompt = f"{prompt}\n\n{addendum}"

        return prompt

    # ---------------- INPUT SELECTOR ----------------

    def _load_input_text(self):
        if self.mode == "teacher":
            path = get_artifact_path(self.session_id, "teacher_transcription.txt")
        else:
            path = get_artifact_path(self.session_id, "transcription.txt")

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

        user_content = body
        if is_qwen3_dense(self.model_name) and not body.lstrip().startswith("/no_think"):
            user_content = "/no_think\n" + body

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

    # ---------------- MAIN PROCESS ----------------

    def process(self, _):

        input_text = self._load_input_text()
        board_text = self._load_board_ocr_text()
        if board_text:
            logger.info(f"Board OCR content found for session {self.session_id} ({len(board_text)} chars); including in summary.")

        summary_path = get_artifact_path(self.session_id, "summary.md")
        StorageManager.save(summary_path, "", append=False)

        prompt = render_summarizer_prompt(
            self.summarizer.tokenizer,
            self._get_message(input_text, board_text)
        )

        start = time.perf_counter()
        first_token_time = None
        raw_tokens = []
        think_filter = StreamThinkFilter()

        try:
            streamer = self.summarizer.generate(prompt, pre_templated=True)
            for token in streamer:
                if first_token_time is None:
                    first_token_time = time.perf_counter()

                raw_tokens.append(token)

                clean_token = think_filter.filter(token)
                if not clean_token:
                    continue

                StorageManager.save_async(summary_path, clean_token, append=True)
                yield clean_token

        finally:
            end = time.perf_counter()
            summarization_time = end - start

            raw_text = "".join(raw_tokens)
            try:
                total_tokens = len(self.summarizer.tokenizer.encode(raw_text)) if raw_text else 0
            except Exception:
                total_tokens = -1

            ttft = (first_token_time - start) if first_token_time else -1

            decode_time = (end - first_token_time) if first_token_time else summarization_time
            tps = ((total_tokens - 1) / decode_time) if decode_time > 0 and total_tokens > 1 else -1

            StorageManager.update_csv(
                path=get_artifact_path(self.session_id, "performance_metrics.csv"),
                new_data={
                    "configuration.summarizer_model": f"{self.provider}/{self.model_name}",
                    "performance.summarizer_time": round(summarization_time, 4),
                    "performance.ttft": f"{round(ttft, 4)}s",
                    "performance.tps": round(tps, 4),
                    "performance.total_tokens": total_tokens,
                    "performance.summarization_time": f"{round(summarization_time, 4)}s",
                }
            )
