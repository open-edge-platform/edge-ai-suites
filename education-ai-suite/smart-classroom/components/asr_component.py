from components.base_component import PipelineComponent
import os
import time
import torch
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.runtime_config_loader import RuntimeConfig
from components.asr.openai.whisper import Whisper as OA_Whisper
from components.asr.openvino.whisper import Whisper as OV_Whisper
from components.asr.funasr.paraformer import Paraformer
import logging
logger = logging.getLogger(__name__)

DELETE_CHUNK_AFTER_USE =  config.pipeline.delete_chunks_after_use
THREADS_LIMIT = config.models.asr.threads_limit
class ASRComponent(PipelineComponent):

    _model = None
    _config = None

    def __init__(self, session_id, provider="openai", model_name="whisper-small", device="CPU", temperature=0.0):

        self.session_id = session_id
        self.temperature = temperature
        self.provider = provider
        self.model_name = model_name
        self.threads_limit = THREADS_LIMIT
        provider, model_name = provider.lower(), model_name.lower()
        config = (provider, model_name, device)

        # Reload only if config changed
        if ASRComponent._model is None or ASRComponent._config != config:
            if provider == "openai" and "whisper" in model_name:
                ASRComponent._model = OA_Whisper(model_name, device, None)
            elif provider == "openvino" and "whisper" in model_name:
                ASRComponent._model = OV_Whisper(model_name, device, None,self.threads_limit)
            elif provider == "funasr" and "paraformer" in model_name:
                ASRComponent._model = Paraformer(model_name, device.lower(), None)
            else:
                raise ValueError(f"Unsupported ASR provider/model: {provider}/{model_name}")
            ASRComponent._config = config

        self.asr = ASRComponent._model

    def process(self, input_generator):

        project_config = RuntimeConfig.get_section("Project")
        project_path = os.path.join(project_config.get("location"), project_config.get("name"), self.session_id)
        StorageManager.save(os.path.join(project_path, "transcription.txt"), "", append=False)

        start_time = time.perf_counter()
        default_torch_threads = None
        try: 
            if self.provider in ["openai", "funasr"] and self.threads_limit and self.threads_limit > 0:
                default_torch_threads = torch.get_num_threads()
                torch.set_num_threads(self.threads_limit)

            for chunk_data in input_generator:
                chunk_path = chunk_data["chunk_path"]
                transcribed_text = self.asr.transcribe(chunk_path, temperature=self.temperature)

                if os.path.exists(chunk_data["chunk_path"]) and DELETE_CHUNK_AFTER_USE:
                    os.remove(chunk_data["chunk_path"])

                StorageManager.save_async(os.path.join(project_path, "transcription.txt"), transcribed_text, append=True)

                yield {
                    **chunk_data,  # keep all chunk metadata
                    "text": transcribed_text
                }
        finally:
            if default_torch_threads is not None:
                torch.set_num_threads(default_torch_threads)
                
            end_time = time.perf_counter()
            transcription_time = end_time - start_time

            # Save the transcription time in the metrics CSV file
            StorageManager.update_csv(
                path=os.path.join(project_path, "performance_metrics.csv"),
                new_data={
                    "configuration.asr_model": f"{self.provider}/{self.model_name}",
                    "performance.transcription_time": round(transcription_time, 4)
                }
            )

            logger.info(f"Transcription Complete: {self.session_id}")

            
