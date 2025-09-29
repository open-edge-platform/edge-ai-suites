from components.llm.base_summarizer import BaseSummarizer
from ipex_llm.transformers import AutoModelForCausalLM
import torch
import threading

from utils.config_loader import config
import logging
logger = logging.getLogger(__name__)

from transformers import TextIteratorStreamer

class Summarizer(BaseSummarizer):
    def __init__(self, model_name, device="xpu", temperature=0.7):
        if config.models.summarizer.model_hub is not None:
            model_hub = config.models.summarizer.model_hub
        else:
            model_hub = "huggingface"

        if model_hub == "huggingface":
            from transformers import AutoTokenizer
        elif model_hub == "modelscope":
            from modelscope import AutoTokenizer
        else:
            raise ValueError(f"Unsupported Model Hub: {model_hub}, should be huggingface or modelscope")

        if not device.startswith("gpu") and device != "cpu":
            raise ValueError(f"Unknown device {device}")
        if device == "gpu" or device == "gpu.0":
            device = "xpu"
        elif device.startswith("gpu.") and device[4:].isdigit():
            device = f"xpu:{device[4:]}"
                
        # Load model
        if config.models.summarizer.use_cache is not None:
            use_cache = config.models.summarizer.use_cache
        else:
            use_cache = True

        if config.models.summarizer.weight_format and config.models.summarizer.weight_format.lower() == "int4":
            logger.info("Loading model in sym_int4 quantization mode.")
            load_in_low_bit = "sym_int4"
        elif config.models.summarizer.weight_format and config.models.summarizer.weight_format.lower() == "int8":
            logger.info("Loading model in sym_int8 quantization mode.")
            load_in_low_bit = "sym_int8"
        elif config.models.summarizer.weight_format and config.models.summarizer.weight_format.lower() == "fp16":
            logger.info("Loading model in fp16 quantization mode.")
            load_in_low_bit = "fp16"
        else:
            logger.info("Loading model in full precision mode.")
            load_in_low_bit = None

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            # load_in_4bit=True,
            load_in_low_bit=load_in_low_bit,
            optimize_model=True,
            trust_remote_code=True,
            use_cache=use_cache,
            model_hub=model_hub
        )
        self.device = device
        self.model = self.model.to(self.device)
        self.model = self.model.eval().to(self.device)

        self.temperature = temperature

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True
        )

    def generate(self, prompt: str, stream: bool = True):
        max_new_tokens = config.models.summarizer.max_new_tokens or 1024

        with torch.inference_mode():
            model_inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            if not stream:
                try:
                    generated_ids = self.model.generate(
                        model_inputs.input_ids,
                        max_new_tokens=max_new_tokens,
                        temperature=self.temperature
                    )
                    torch.xpu.empty_cache()
                    torch.xpu.synchronize()
                    generated_ids = generated_ids.cpu()
                    generated_ids = [
                        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                    ]

                    response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                    return response
                except Exception as e:
                    logger.error(f"Error during generation: {e}")
                    return None
            else:
                try:

                    class CountingTextIteratorStreamer(TextIteratorStreamer):
                        def __init__(self, tokenizer, skip_special_tokens=True, skip_prompt=True):
                            super().__init__(tokenizer, skip_special_tokens=skip_special_tokens, skip_prompt=skip_prompt)
                            self.total_tokens = 0

                        def put(self, value):
                            self.total_tokens += 1
                            super().put(value)

                    streamer = CountingTextIteratorStreamer(self.tokenizer, skip_special_tokens=True, skip_prompt=True)
                    gen_kwargs = dict(
                        input_ids=model_inputs.input_ids,
                        max_new_tokens=max_new_tokens,
                        temperature=self.temperature,
                        streamer=streamer
                    )

                    torch.xpu.empty_cache()
                    torch.xpu.synchronize()
                    
                    thread = threading.Thread(target=self.model.generate, kwargs=gen_kwargs)
                    thread.start()
                    return streamer
                except Exception as e:
                    logger.error(f"Error during streaming generation: {e}")
                    return None