from components.base_component import PipelineComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.markdown_cleaner import StreamThinkFilter
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
        
        text_gen = config.models.text_gen
        SummarizerComponent._model = ModelManager.instance().text_gen()
        SummarizerComponent._config = ("vlm", text_gen.vlm_name, text_gen.device)

        self.summarizer = SummarizerComponent._model
        self.model_name = text_gen.vlm_name
        self.provider = text_gen.provider

    # ---------------- SYSTEM PROMPT SELECTOR ----------------

    def _get_system_prompt(self):
        lang = config.app.language
        prompts = vars(config.models.summarizer.system_prompt)[lang]

        if self.mode == "teacher":
            return prompts.Teacher
        elif self.mode == "hybrid":
            return prompts.Hybrid
        else:
            return prompts.Dialog

    # ---------------- INPUT SELECTOR ----------------

    def _load_input_text(self):
        project_config = RuntimeConfig.get_section("Project")
        project_path = os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            self.session_id
        )

        if self.mode == "teacher":
            path = os.path.join(project_path, "teacher_transcription.txt")
        else:
            path = os.path.join(project_path, "transcription.txt")

        return StorageManager.read_text_file(path)

    # ---------------- MESSAGE BUILDER ----------------

    def _get_message(self, input_text):
        system_prompt = self._get_system_prompt()
        logger.debug(f"Summarizer mode: {self.mode}")
        logger.debug(f"System Prompt Loaded")

        user_content = input_text
        if "qwen3" in str(self.model_name).lower() and not input_text.lstrip().startswith("/no_think"):
            user_content = "/no_think\n" + input_text

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

    # ---------------- MAIN PROCESS ----------------

    def process(self, _):

        input_text = self._load_input_text()

        project_config = RuntimeConfig.get_section("Project")
        project_path = os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            self.session_id
        )

        summary_path = os.path.join(project_path, "summary.md")
        StorageManager.save(summary_path, "", append=False)

        prompt = self.summarizer.tokenizer.apply_chat_template(
            self._get_message(input_text),
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )

        start = time.perf_counter()
        first_token_time = None
        raw_tokens = []
        think_filter = StreamThinkFilter()

        try:
            streamer = self.summarizer.generate(prompt)
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
                path=os.path.join(project_path, "performance_metrics.csv"),
                new_data={
                    "configuration.summarizer_model": f"{self.provider}/{self.model_name}",
                    "performance.summarizer_time": round(summarization_time, 4),
                    "performance.ttft": f"{round(ttft, 4)}s",
                    "performance.tps": round(tps, 4),
                    "performance.total_tokens": total_tokens,
                    "performance.summarization_time": f"{round(summarization_time, 4)}s",
                }
            )
