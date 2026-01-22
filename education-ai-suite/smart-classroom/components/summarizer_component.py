from components.base_component import PipelineComponent
from components.llm.openvino.summarizer import Summarizer as OvSummarizer
from components.llm.ipex.summarizer import Summarizer as IpexSummarizer
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
import logging, os
import time

logger = logging.getLogger(__name__)

class SummarizerComponent(PipelineComponent):
    _model = None
    _config = None

    def __init__(self, session_id, provider, model_name, device, temperature=0.7, mode="dialog"):
        self.session_id = session_id
        self.mode = mode.lower()
        provider = provider.lower()
        cfg = (provider, model_name, device)

        # Reload only if config changed
        if SummarizerComponent._model is None or SummarizerComponent._config != cfg:
            if provider == "openvino":
                SummarizerComponent._model = OvSummarizer(
                    model_name=model_name,
                    device=device,
                    temperature=temperature,
                    revision=None
                )
            elif provider == "ipex":
                SummarizerComponent._model = IpexSummarizer(
                    model_name=model_name,
                    device=device.lower(),
                    temperature=temperature
                )
            else:
                raise ValueError(f"Unsupported summarizer provider: {provider}")

            SummarizerComponent._config = cfg

        self.summarizer = SummarizerComponent._model
        self.model_name = model_name
        self.provider = provider

    # ---------------- SYSTEM PROMPT SELECTOR ----------------

    def _get_system_prompt(self):
        lang = config.models.summarizer.language
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

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text}
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
            add_generation_prompt=True
        )

        start = time.perf_counter()
        first_token_time = None
        streamer = None

        try:
            streamer = self.summarizer.generate(prompt)
            for token in streamer:
                if first_token_time is None:
                    first_token_time = time.perf_counter()

                StorageManager.save_async(summary_path, token, append=True)
                yield token

        finally:
            end = time.perf_counter()
            total_tokens = streamer.total_tokens if streamer else -1
            summarization_time = end - start
            ttft = (first_token_time - start) if first_token_time else -1
            tps = (total_tokens / summarization_time) if summarization_time > 0 else -1

            performance_data = StorageManager.read_performance_metrics(
                project_config.get("location"),
                project_config.get("name"),
                self.session_id
            )

            performance_metrics = performance_data.get("performance", {})
            asr_time = performance_metrics.get("transcription_time", 0)
            end_to_end_time = asr_time + summarization_time

            StorageManager.update_csv(
                path=os.path.join(project_path, "performance_metrics.csv"),
                new_data={
                    "configuration.summarizer_model": f"{self.provider}/{self.model_name}",
                    "performance.summarizer_time": round(summarization_time, 4),
                    "performance.ttft": f"{round(ttft, 4)}s",
                    "performance.tps": round(tps, 4),
                    "performance.total_tokens": total_tokens,
                    "performance.end_to_end_time": f"{round(end_to_end_time, 4)}s",
                }
            )
