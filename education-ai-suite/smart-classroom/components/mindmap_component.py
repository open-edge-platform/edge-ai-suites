from components.base_component import PipelineComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
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
        logger.debug(f"Mindmap System Prompt: {lang_prompt.get(config.models.summarizer.language)}")
        return [
            {"role": "system", "content": f"{lang_prompt.get(config.models.summarizer.language)}"},
            {"role": "user", "content": f"{input_text}"}
        ]

    def generate_mindmap(self, summary_text):
        project_config = RuntimeConfig.get_section("Project")
        project_path = os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            self.session_id
        )
        mindmap_path = os.path.join(project_path, "mindmap.mmd")

        try:
            logger.info("Generating mindmap from summary...")
            mindmap_prompt = self.model.tokenizer.apply_chat_template(
                self._get_mindmap_message(summary_text),
                tokenize=False,
                add_generation_prompt=True
            )

            mindmap_streamer = self.model.generate(mindmap_prompt)
            full_mindmap = "".join(token for token in mindmap_streamer)
            StorageManager.save(mindmap_path, full_mindmap, append=False)
            logger.info("Mindmap generation completed successfully.")
            return full_mindmap

        except Exception as e:
            logger.error(f"Mindmap generation failed: {e}")
            raise e