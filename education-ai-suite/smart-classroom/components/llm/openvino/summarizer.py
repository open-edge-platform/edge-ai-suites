from components.llm.base_summarizer import BaseSummarizer
import logging
from transformers import AutoTokenizer, TextIteratorStreamer
from optimum.intel.openvino import OVModelForCausalLM
from utils import ensure_model
from utils.config_loader import config
from utils.locks import audio_pipeline_lock
import threading

logger = logging.getLogger(__name__)


class Summarizer(BaseSummarizer):
    def __init__(self, model_name, device, temperature=0.7, revision=None):
        self.model_name = model_name
        self.device = device.upper()  # OpenVINO uses "GPU" or "CPU"
        self.temperature = temperature

        model_path = ensure_model.get_model_path()
        logger.info(f"Loading Model: model name={self.model_name}, model path={model_path}, device={self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, 
            trust_remote_code=True, 
            fix_mistral_regex=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        self.model = OVModelForCausalLM.from_pretrained(
            model_path, 
            device=self.device, 
            use_cache=True
        )

    def generate(self, prompt: str, stream: bool = True):
        max_new_tokens = config.models.summarizer.max_new_tokens
        inputs = self.tokenizer(prompt, return_tensors="pt")
        class CountingTextIteratorStreamer(TextIteratorStreamer):
                def __init__(self, tokenizer, skip_special_tokens=True, skip_prompt=True):
                    super().__init__(tokenizer, skip_special_tokens=skip_special_tokens, skip_prompt=skip_prompt)
                    self.total_tokens = 0

                def put(self, value):
                    if value is not None:
                        self.total_tokens += 1
                    super().put(value)

        streamer = CountingTextIteratorStreamer(
            self.tokenizer, 
            skip_special_tokens=True, 
            skip_prompt=True
        )
            
        def run_generation():
            with audio_pipeline_lock:
                generation_kwargs = {
                    "input_ids": inputs.input_ids,
                    "max_new_tokens": max_new_tokens,
                    "temperature": self.temperature,
                    "do_sample": True,
                    "top_p": 0.9,
                    "streamer": streamer,
                    "pad_token_id": self.tokenizer.eos_token_id
                }
                self.model.generate(**generation_kwargs)
        
        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()
        
        return streamer