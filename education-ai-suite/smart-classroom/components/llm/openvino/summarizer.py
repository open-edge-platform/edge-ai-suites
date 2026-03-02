from components.llm.base_summarizer import BaseSummarizer
import logging, threading, gc
from transformers import AutoTokenizer, TextIteratorStreamer
from optimum.intel.openvino import OVModelForCausalLM
from utils import ensure_model
from utils.config_loader import config
from utils.locks import audio_pipeline_lock

logger = logging.getLogger(__name__)


class Summarizer(BaseSummarizer):
    def __init__(self, model_name, device, temperature=0.7, revision=None):
        self.model_name = model_name
        self.device = device.upper()
        self.temperature = temperature

        self.model_path = ensure_model.get_model_path()

        logger.info(
            f"Summarizer initialized (lazy load). "
            f"model={self.model_name}, path={self.model_path}, device={self.device}"
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            fix_mistral_regex=True,
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _load_model(self):
        logger.info("Loading OVModelForCausalLM instance...")
        return OVModelForCausalLM.from_pretrained(
            self.model_path,
            device=self.device,
            use_cache=True,
        )

    def _destroy_model(self, model):
        try:
            del model
            gc.collect()
            logger.info("OV model instance destroyed")
        except Exception as e:
            logger.warning(f"Failed to destroy OV model cleanly: {e}")

    def generate(self, prompt: str, stream: bool = True):
        max_new_tokens = config.models.summarizer.max_new_tokens
        inputs = self.tokenizer(prompt, return_tensors="pt")

        if stream:
            class CountingTextIteratorStreamer(TextIteratorStreamer):
                def __init__(self, tokenizer, skip_special_tokens=True, skip_prompt=True):
                    super().__init__(
                        tokenizer,
                        skip_special_tokens=skip_special_tokens,
                        skip_prompt=skip_prompt,
                    )
                    self.total_tokens = 0

                def put(self, value):
                    if value is not None:
                        self.total_tokens += 1
                    super().put(value)

            streamer = CountingTextIteratorStreamer(
                self.tokenizer,
                skip_special_tokens=True,
                skip_prompt=True,
            )

            def run_generation():
                model = None
                try:
                    with audio_pipeline_lock:
                        model = self._load_model()
                        model.generate(
                            input_ids=inputs.input_ids,
                            max_new_tokens=max_new_tokens,

                            # sampling
                            do_sample=True,
                            temperature=max(self.temperature, 0.1),
                            top_p=0.9,
                            top_k=50,

                            # tokens
                            pad_token_id=self.tokenizer.eos_token_id,
                            eos_token_id=self.tokenizer.eos_token_id,

                            # streaming
                            streamer=streamer,
                        )

                except Exception:
                    logger.error(
                        "Exception occurred in OV streaming generation",
                        exc_info=True,
                    )
                    if hasattr(streamer, "_queue"):
                        streamer._queue.put(
                            "[ERROR]: Summary generation failed due to resource constraints."
                        )

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
                        input_ids=inputs.input_ids,
                        max_new_tokens=max_new_tokens,

                        do_sample=True,
                        temperature=max(self.temperature, 0.1),
                        top_p=0.9,
                        top_k=50,

                        pad_token_id=self.tokenizer.eos_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                    )
            finally:
                if model is not None:
                    self._destroy_model(model)
