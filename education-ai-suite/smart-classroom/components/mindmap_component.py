from components.base_component import PipelineComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.prompt_loader import load_prompt
from utils.storage_manager import StorageManager
from utils.session_paths import SessionPaths
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
        system_prompt = load_prompt("mindmap", config.app.language, "system_prompt")
        logger.debug("Mindmap system prompt loaded for lang=%s", config.app.language)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{input_text}"}
        ]

    def generate_mindmap(self, summary_text):
        mindmap_path = str(SessionPaths.mindmap_path(self.session_id))

        try:
            logger.info("Generating mindmap from summary...")
            full_mindmap = self.model.generate(
                messages=self._get_mindmap_message(summary_text),
                stream=False,
                enable_thinking=False,
            )
            StorageManager.save(mindmap_path, full_mindmap, append=False)
            logger.info("Mindmap generation completed successfully.")
            return full_mindmap

        except Exception as e:
            logger.error(f"Mindmap generation failed: {e}")
            raise e