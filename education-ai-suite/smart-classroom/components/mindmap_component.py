from components.base_component import PipelineComponent
from components.llm.openvino.summarizer import Summarizer as OvSummarizer
from components.llm.ipex.summarizer import Summarizer as IpexSummarizer
from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.storage_manager import StorageManager
import logging, os

logger = logging.getLogger(__name__)

class MindmapComponent(PipelineComponent):
    _model = None
    _config = None

    def __init__(self, session_id, provider, model_name, device, temperature=0.7):
        self.session_id = session_id
        provider = provider.lower()
        config_key = (provider, model_name, device)

        if MindmapComponent._model is None or MindmapComponent._config != config_key:
            if provider == "openvino":
                MindmapComponent._model = OvSummarizer(
                    model_name=model_name,
                    device=device,
                    temperature=temperature,
                    revision=None
                )
            elif provider == "ipex":
                MindmapComponent._model = IpexSummarizer(
                    model_name=model_name,
                    device=device.lower(),
                    temperature=temperature
                )
            else:
                raise ValueError(f"Unsupported summarizer provider: {provider}")

            MindmapComponent._config = config_key

        self.summarizer = MindmapComponent._model
        self.model_name = model_name
        self.provider = provider

    def _get_mindmap_message(self, input_text):
        lang_prompt = vars(config.mindmap.system_prompt)
        logger.debug(f"Mindmap System Prompt: {lang_prompt.get(config.models.summarizer.language)}")
        return [
            {"role": "system", "content": f"{lang_prompt.get(config.models.summarizer.language)}"},
            {"role": "user", "content": f"{input_text}"}
        ]

    def generate_mindmap(self, summary_text):
        """
        Generate a complete mindmap string (non-streaming).
        """
        project_config = RuntimeConfig.get_section("Project")
        project_path = os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            self.session_id
        )
        mindmap_path = os.path.join(project_path, "mindmap.mmd")

        try:
            logger.info("Generating mindmap from summary...")
            mindmap_prompt = self.summarizer.tokenizer.apply_chat_template(
                self._get_mindmap_message(summary_text),
                tokenize=False,
                add_generation_prompt=True
            )

            # Generate tokens
            mindmap_streamer = self.summarizer.generate(mindmap_prompt)
            full_mindmap = "".join(token for token in mindmap_streamer)

            # Save full mindmap to file
            StorageManager.save(mindmap_path, full_mindmap, append=False)
            logger.info("Mindmap generation completed successfully.")
            return full_mindmap

        except Exception as e:
            logger.error(f"Mindmap generation failed: {e}")
            raise e
