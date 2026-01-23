from fastapi import HTTPException, status
import re
from components.stream_reader import AudioStreamReader
from components.asr_component import ASRComponent
from utils.config_loader import config
import logging, os
from utils.session_manager import generate_session_id
from components.summarizer_component import SummarizerComponent
from components.mindmap_component import MindmapComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
from utils.markdown_cleaner import markdown_to_plain
from monitoring import monitor
import time
logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self, session_id=None):
        logger.info("pipeline initialized")
        self.session_id = session_id or generate_session_id()
        # Bind models during construction
        self.transcription_pipeline = [
            AudioStreamReader(self.session_id),
            ASRComponent(self.session_id, provider=config.models.asr.provider, model_name=config.models.asr.name, device=config.models.asr.device, temperature=config.models.asr.temperature) 
        ]

        self.summarizer_pipeline = [
            SummarizerComponent(self.session_id, provider=config.models.summarizer.provider, model_name=config.models.summarizer.name, temperature=config.models.summarizer.temperature, device=config.models.summarizer.device, mode=config.models.summarizer.mode)
        ]

        self.mindmap_component = MindmapComponent(
                self.session_id,
                provider=config.models.summarizer.provider,
                model_name=config.models.summarizer.name, 
                device=config.models.summarizer.device,
                temperature=config.models.summarizer.temperature,
            )
        
        self.mindmap_component.model = self.summarizer_pipeline[0].summarizer

    def run_transcription(self, input):
        project_config = RuntimeConfig.get_section("Project")
        input_gen = ({"input": input} for _ in range(1))

        for component in self.transcription_pipeline:
            input_gen = component.process(input_gen)

        try:
            for chunk_trancription in input_gen:
                yield chunk_trancription
        finally:
            pass
            
    
    def run_summarizer(self):

        project_config = RuntimeConfig.get_section("Project")
        transcription_path = os.path.join(project_config.get("location"), project_config.get("name"), self.session_id, "transcription.txt")

        try:
            input = StorageManager.read_text_file(transcription_path)
            if not input:
                logger.error(f"Transcription is empty. No content available for summarization.")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transcription is empty. No content available for summarization.")
        except FileNotFoundError:
            logger.error(f"Invalid Session ID: {self.session_id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid session id: {self.session_id}, transcription not found.")
        except Exception:
            logger.error(f"An unexpected error occurred while accessing the transcription.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while accessing the transcription.")
        
        for component in self.summarizer_pipeline:
            input = component.process(input)

        try:
            for token in input:
                yield token
        finally: 
            pass 

    def run_mindmap(self):

        project_config = RuntimeConfig.get_section("Project")
        session_dir = os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            self.session_id
        )
        summary_path = os.path.join(session_dir, "summary.md")
        min_tokens = config.mindmap.min_token

        try:
            summary_md = StorageManager.read_text_file(summary_path)

            if not summary_md:
                logger.error("Summary is empty. Cannot generate mindmap.")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Summary is empty. Cannot generate mindmap."
                )

        except FileNotFoundError:
            logger.error(f"Invalid Session ID: {self.session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid session id: {self.session_id}, summary not found."
            )
        except Exception as e:
            logger.error(f"Unexpected error while accessing summary: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while accessing the summary."
            )
        summary_plain = markdown_to_plain(summary_md)

        token_count = len(re.findall(r'[\u4e00-\u9fff]|[^\u4e00-\u9fff\s]+', summary_plain))
        logger.info(f"Summary token count: {token_count}, Minimum required: {min_tokens}")

        if token_count < min_tokens:
            logger.warning("Insufficient information to generate mindmap.")
            insufficient_mindmap = {
                "meta": {
                    "name": "insufficient_input",
                    "author": "ai_assistant",
                    "version": "1.0"
                },
                "format": "node_tree",
                "data": {
                    "id": "root",
                    "topic": "Insufficient Input",
                    "children": [
                        {
                            "id": "insufficient_info",
                            "topic": "Insufficient Information",
                            "children": [
                                {
                                    "id": "short_summary",
                                    "topic": "The summary is too short to generate a meaningful mindmap"
                                },
                                {
                                    "id": "token_info",
                                    "topic": f"Current tokens: {token_count}, Required: {min_tokens}"
                                }
                            ]
                        }
                    ]
                }
            }
            
            # Convert to JSON string
            import json
            insufficient_mindmap_json = json.dumps(insufficient_mindmap, indent=2)
            
            mindmap_path = os.path.join(session_dir, "mindmap.mmd")
            StorageManager.save(mindmap_path, insufficient_mindmap_json, append=False)
            return insufficient_mindmap_json

        try:
            full_mindmap = self.mindmap_component.generate_mindmap(summary_plain)
            logger.info("Mindmap generation successful.")
            return full_mindmap

        except Exception as e:
            logger.error(f"Error during mindmap generation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error during mindmap generation: {e}"
            )
        finally:
            pass