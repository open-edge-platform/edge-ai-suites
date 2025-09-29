from components.llm.base_summarizer import BaseSummarizer
import openvino_genai as ov_genai
from transformers import AutoTokenizer
import logging, threading
from utils import ensure_model
from utils.config_loader import config
from utils.ov_genai_util import YieldingTextStreamer
logger = logging.getLogger(__name__)

class Summarizer(BaseSummarizer):
    def __init__(self, model_name, device, temperature=0.7, revision=None):
        self.model_name = model_name
        self.device = device
        self.temperature = temperature
        logger.info(f"Loading Model: model name={self.model_name}, model path={ensure_model.get_model_path()}, device={self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(ensure_model.get_model_path())
        self.model = ov_genai.LLMPipeline(ensure_model.get_model_path(), device=device)

    def generate(self, prompt):
        streamer = YieldingTextStreamer(self.tokenizer)

        def run_generation():
            try:
                self.model.generate(
                    prompt,
                    streamer=streamer,
                    max_new_tokens=config.models.summarizer.max_new_tokens,
                    temperature=self.temperature,
                )
                
            except Exception as e:
                error_msg = "Summary generation failed. Please ensure sufficient free resources are available to run this process."
                logger.error(f"Exception occured in summary generation: {str(e)}")
                if "out of gpu resources" in str(e).lower():
                    error_msg = "Summary generation failed. Insufficient GPU resources available to run this process."
                streamer._queue.put(f"[ERROR]: {error_msg}")
            finally:
                streamer.end()

        threading.Thread(target=run_generation, daemon=True).start()
        return streamer
