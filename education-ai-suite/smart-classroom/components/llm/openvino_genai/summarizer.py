from components.llm.base_summarizer import BaseSummarizer
import openvino_genai as ov_genai
from transformers import AutoTokenizer
import logging, threading, gc
from utils import ensure_model
from utils.config_loader import config
from utils.ov_genai_util import YieldingTextStreamer
from utils.locks import audio_pipeline_lock
logger = logging.getLogger(__name__)

class Summarizer(BaseSummarizer):
    def __init__(self, model_name, device, temperature=0.7, revision=None):
        self.model_name = model_name
        self.device = device
        self.temperature = temperature
        logger.info(f"Loading Model: model name={self.model_name}, model path={ensure_model.get_model_path()}, device={self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(ensure_model.get_model_path())

    def generate(self, prompt, stream: bool = True):
        if stream:
            streamer = YieldingTextStreamer(self.tokenizer)

            def run_generation():
                model = None
                try:
                    with audio_pipeline_lock:
                        model = self._load_model()
                        model.generate(
                            prompt,
                            streamer=streamer,
                            max_new_tokens=config.models.summarizer.max_new_tokens,
                            temperature=self.temperature,
                            do_sample=False,
                        )
                        cfg = model.get_generation_config()
                        for attr in dir(cfg):
                            if not attr.startswith("_"):
                                logger.info(f"  {attr}: {getattr(cfg, attr)}")
                    
                except Exception as e:
                    error_msg = "Summary generation failed. Please ensure sufficient free resources are available to run this process."
                    logger.error(f"Exception occured in summary generation")
                    if "out of gpu resources" in str(e).lower():
                        error_msg = "Summary generation failed. Insufficient GPU resources available to run this process."
                    streamer._queue.put(f"[ERROR]: {error_msg}")
                finally:
                    if model is not None:
                        self._destroy_model(model)
                    streamer.end()

            threading.Thread(target=run_generation, daemon=True).start()
            return streamer
        else:
            model = None
            try:
                with audio_pipeline_lock:
                    model = self._load_model()
                    return model.generate(
                        prompt,
                        max_new_tokens=config.models.summarizer.max_new_tokens,
                        temperature=self.temperature,
                        do_sample=False,
                    )
            finally:
                if model is not None:
                    self._destroy_model(model)
            
    def _load_model(self):
        logger.info("Loading model instance...")
        return ov_genai.LLMPipeline(ensure_model.get_model_path(), device=self.device)

    def _destroy_model(self, model):
        try:
            del model
            gc.collect()
            logger.info("Model instance destroyed and memory reclaimed")
        except Exception as e:
            logger.warning(f"Failed to fully destroy model: {e}")
