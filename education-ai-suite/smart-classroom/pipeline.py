from fastapi import HTTPException, status
from components.stream_reader import AudioStreamReader
from components.asr_component import ASRComponent
from utils.config_loader import config
import logging, os
from utils.session_manager import generate_session_id
from components.summarizer_component import SummarizerComponent
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
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
            SummarizerComponent(self.session_id, provider=config.models.summarizer.provider, model_name=config.models.summarizer.name, temperature=config.models.summarizer.temperature, device=config.models.summarizer.device)
        ]

    def run_transcription(self, audio_path: str):
        project_config = RuntimeConfig.get_section("Project")
        monitor.start_monitoring(os.path.join(project_config.get("location"), project_config.get("name"), self.session_id, "utilization_logs"))

        input_gen = ({"audio_path": audio_path} for _ in range(1))

        for component in self.transcription_pipeline:
            input_gen = component.process(input_gen)

        try:
            for chunk_trancription in input_gen:
                yield chunk_trancription
        finally:
            monitor.stop_monitoring()
            time.sleep(3) #time for socwatch to get clean-start
            
    
    def run_summarizer(self):

        project_config = RuntimeConfig.get_section("Project")
        transcription_path = os.path.join(project_config.get("location"), project_config.get("name"), self.session_id, "transcription.txt")
        monitor.start_monitoring(os.path.join(project_config.get("location"), project_config.get("name"), self.session_id, "utilization_logs"))

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
            monitor.stop_monitoring()            
            
