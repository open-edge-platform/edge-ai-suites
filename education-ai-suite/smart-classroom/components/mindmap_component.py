from components.base_component import PipelineComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.artifacts.path import get_artifact_path
from utils.markdown_cleaner import strip_think_tokens
from utils.prompt_budget import render_summarizer_prompt
import logging, os
import time

logger = logging.getLogger(__name__)

class MindmapComponent(PipelineComponent):
    def __init__(self, session_id, provider, model_name, device, temperature=0.7):
        self.session_id = session_id
        self.provider = provider.lower()
        self.model_name = model_name
        self.device = device
        self.temperature = temperature

    def _get_mindmap_message(self, input_text):
        lang_prompt = vars(config.mindmap.system_prompt)
        logger.debug(f"Mindmap System Prompt: {lang_prompt.get(config.app.language)}")
        return [
            {"role": "system", "content": f"{lang_prompt.get(config.app.language)}"},
            {"role": "user", "content": f"{input_text}"}
        ]

    def generate_mindmap(self, summary_text):
        mindmap_path = get_artifact_path(self.session_id, "mindmap.mmd")

        try:
            logger.info("Generating mindmap from summary...")
            mindmap_prompt = render_summarizer_prompt(
                self.model.tokenizer,
                self._get_mindmap_message(summary_text)
            )

            start = time.perf_counter()
            full_mindmap = self.model.generate(
                mindmap_prompt, stream=False, pre_templated=True
            )
            elapsed = time.perf_counter() - start
            # Non-streaming output bypasses StreamThinkFilter, so strip any
            # reasoning block here before the JSON is parsed downstream.
            full_mindmap = strip_think_tokens(full_mindmap)
            StorageManager.save(mindmap_path, full_mindmap, append=False)
            self._record_metrics(full_mindmap, elapsed)
            logger.info("Mindmap generation completed successfully.")
            return full_mindmap

        except Exception as e:
            logger.error(f"Mindmap generation failed: {e}")
            raise e

    def _record_metrics(self, mindmap_text: str, elapsed: float) -> None:
        """Append mind-map generation cost to ``performance_metrics.csv``.

        Mind map is the longest generation in the pipeline but used to report
        only its stage duration, so there was no way to tell a slow model from a
        verbose one. There is no TTFT here: this call is non-streaming, so the
        first token is not observable. Never raises — a metrics failure must not
        lose an already-generated mind map.
        """
        try:
            tokens = len(self.model.tokenizer.encode(mindmap_text)) if mindmap_text else 0
        except Exception:
            tokens = -1
        tps = ((tokens - 1) / elapsed) if elapsed > 0 and tokens > 1 else -1

        try:
            StorageManager.update_csv(
                path=get_artifact_path(self.session_id, "performance_metrics.csv"),
                new_data={
                    "configuration.mindmap_model": f"{self.provider}/{self.model_name}",
                    "performance.mindmap_time": round(elapsed, 4),
                    "performance.mindmap_tps": round(tps, 4),
                    "performance.mindmap_total_tokens": tokens,
                    "performance.mindmap_generation_time": f"{round(elapsed, 4)}s",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to record mindmap performance metrics: {e}")