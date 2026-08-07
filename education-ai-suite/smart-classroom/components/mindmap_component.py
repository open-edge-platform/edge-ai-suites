from components.base_component import PipelineComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.artifacts.path import get_artifact_path
from utils.markdown_cleaner import strip_think_tokens
from utils.prompt_budget import render_summarizer_prompt
import logging, os

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

            full_mindmap = self.model.generate(
                mindmap_prompt, stream=False, pre_templated=True
            )
            # Non-streaming output bypasses StreamThinkFilter, so strip any
            # reasoning block here before the JSON is parsed downstream.
            full_mindmap = strip_think_tokens(full_mindmap)
            StorageManager.save(mindmap_path, full_mindmap, append=False)
            logger.info("Mindmap generation completed successfully.")
            return full_mindmap

        except Exception as e:
            logger.error(f"Mindmap generation failed: {e}")
            raise e