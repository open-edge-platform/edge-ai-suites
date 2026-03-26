# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
import time
import uuid
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread
from typing import Optional

import openvino_genai as ov_genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_utils.tasks import repeat_every
from optimum.intel.openvino import OVModelForVisualCausalLM
from qwen_vl_utils import process_vision_info
from utils.common import ErrorMessages, ModelNames, logger, settings
from utils.data_models import (
    ChatCompletionChoice,
    ChatCompletionDelta,
    ChatCompletionResponse,
    ChatRequest,
    MessageContentImageUrl,
    MessageContentText,
)
from utils.utils import (
    convert_model,
    is_model_ready,
    load_images,
    load_model_config,
    setup_seed,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from transformers import AutoProcessor, AutoTokenizer, TextIteratorStreamer

# Suppress specific warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


from multiprocessing import Manager

manager = Manager()
active_requests = manager.Value("i", 0)
queued_requests = manager.Value("i", 0)
request_lock = manager.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None
    """

    @repeat_every(seconds=2)
    async def log_request_counts():
        if active_requests.value > 0 or queued_requests.value > 0:
            logger.info(
                f"Active requests: {active_requests.value}, Queued requests: {queued_requests.value}"
            )

    log_task = asyncio.create_task(log_request_counts())
    yield
    log_task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("VLM_CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=os.getenv("VLM_CORS_ALLOW_METHODS", "*").split(","),
    allow_headers=os.getenv("VLM_CORS_ALLOW_HEADERS", "*").split(","),
)


class RequestQueueMiddleware(BaseHTTPMiddleware):
    """
    Middleware to manage request queuing and active request tracking.
    """

    def __init__(self, app):
        """
        Initialize the middleware.

        Args:
            app: The FastAPI application instance.
        """
        super().__init__(app)
        logger.info(f"RequestQueueMiddleware initialized in process: {os.getpid()}")

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/v1/chat/completions":
            with request_lock:
                queued_requests.value += 1
            try:
                with request_lock:
                    active_requests.value += 1
                    queued_requests.value -= 1
                response = await call_next(request)
            finally:
                with request_lock:
                    active_requests.value -= 1
        else:
            response = await call_next(request)
        return response


app.add_middleware(RequestQueueMiddleware)


model_ready = False
pipe, processor, model_dir = None, None, None


def cleanup_pipeline_state():
    """Release any cached runtime state held by the global pipeline."""
    global pipe
    if pipe is None:
        return

    cleanup_methods = (
        "clear_requests",
        "reset_state",
        "reset",
        "release_kv_cache",
        "clear_cache",
    )
    for method in cleanup_methods:
        if hasattr(pipe, method):
            try:
                getattr(pipe, method)()
                logger.debug(f"Pipeline state cleared using '{method}'.")
                return
            except Exception as exc:
                logger.warning(f"Failed to run pipeline cleanup via '{method}': {exc}")
    logger.debug("No cleanup method available on pipeline instance.")


def wait_for_generation_thread(thread: Optional[Thread], timeout: float = 2.0):
    """Join a generation thread to make sure resources are released."""
    if thread is None:
        return
    if not thread.is_alive():
        return
    thread.join(timeout=timeout)
    if thread.is_alive():
        logger.warning("Generation thread did not terminate within timeout.")


def restart_server():
    """
    Restart the API server.

    Raises:
        RuntimeError: If the server fails to restart.
    """
    try:
        logger.info("Restarting the API server...")
        os.execv(
            sys.executable, ["python"] + sys.argv
        )  # Restart the current Python script
    except Exception as e:
        logger.error(f"Failed to restart the server: {e}")
        raise RuntimeError(f"Failed to restart the server: {e}")


# Initialize the model
def initialize_model():
    """
    Initialize the model by loading it and setting up the processor.

    Raises:
        RuntimeError: If there is an error during model initialization.
    """
    global model_ready
    global pipe, processor, model_dir
    model_name = settings.VLM_MODEL_NAME
    model_dir = Path(model_name.split("/")[-1])
    model_dir = Path("ov-model") / model_dir
    model_dir.mkdir(parents=True, exist_ok=True)
    weight = settings.VLM_COMPRESSION_WEIGHT_FORMAT.lower()
    model_dir = model_dir / weight
    logger.info(f"Model_name: {model_name} \b Compression_Weight_Format: {weight}")

    try:
        if not is_model_ready(model_dir):
            convert_model(
                model_name,
                str(model_dir),
                model_type="vlm",
                weight_format=weight,
            )
    except Exception as e:
        logger.error(f"Error initializing the model: {e}")
        raise RuntimeError(f"Error initializing the model: {e}")

    try:
        model_config = load_model_config(model_name.split("/")[-1].lower())
        ov_config = settings.get_ov_config_dict()
        logger.debug(f"Using OpenVINO configuration: {ov_config}")
        if ModelNames.PHI in model_name.lower():
            pipe = OVModelForVisualCausalLM.from_pretrained(
                model_dir,
                device=settings.VLM_DEVICE.upper(),
                trust_remote_code=True,
                use_cache=False,
                ov_config=ov_config,
            )
            processor = AutoProcessor.from_pretrained(
                model_name, trust_remote_code=True
            )
        elif ModelNames.QWEN in model_name.lower():
            if not model_config:
                raise RuntimeError("Model configuration is empty or invalid.")
            pipe = OVModelForVisualCausalLM.from_pretrained(
                model_dir,
                device=settings.VLM_DEVICE.upper(),
                trust_remote_code=True,
                use_cache=False,
                ov_config=ov_config,
            )
            processor = AutoProcessor.from_pretrained(
                model_dir,
                trust_remote_code=True,
                min_pixels=int(eval(model_config.get("min_pixels"))),
                max_pixels=int(eval(model_config.get("max_pixels"))),
            )
        else:
            pipe = ov_genai.VLMPipeline(
                model_dir, device=settings.VLM_DEVICE.upper(), **ov_config
            )
            processor = None  # No processor needed for this case
        model_ready = is_model_ready(model_dir)
        logger.debug("Model is ready")
    except Exception as e:
        logger.error(f"Error initializing the model: {e}")
        raise RuntimeError(f"Error initializing the model: {e}")


# Initialize the model to create global objects of processor, model, model_ready
initialize_model()


def safe_generate(pipe, generation_kwargs, streamer):
    """
    Safely call the `generate` method of the pipeline and handle exceptions.

    Args:
        pipe: The model pipeline.
        generation_kwargs: The generation configuration arguments.
        streamer: The streamer to handle output tokens.
    """
    try:
        pipe.generate(**generation_kwargs)
    except Exception as e:
        logger.error(f"Exception in thread during generation: {e}")
        if ErrorMessages.GPU_OOM_ERROR_MESSAGE in str(e):
            logger.error("Detected GPU out-of-memory error, restarting server...")
            restart_server()
    finally:
        streamer.end_of_stream = True


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """Handle chat completion requests (text + image_url content only, non-streaming)."""
    try:
        seed = request.seed if request.seed is not None else settings.SEED
        setup_seed(seed)

        global pipe, processor, model_dir
        logger.info("Received a chat completion request.")

        # Extract prompt and image URLs from the last user message
        last_user_message = next(
            (m for m in reversed(request.messages) if m.role == "user"), None
        )

        image_urls, prompt = [], None
        if last_user_message:
            if isinstance(last_user_message.content, str):
                prompt = last_user_message.content
            else:
                for content in last_user_message.content:
                    if isinstance(content, MessageContentImageUrl):
                        image_urls.append(content.image_url.get("url"))
                    elif isinstance(content, MessageContentText):
                        prompt = content.text
                    elif isinstance(content, str):
                        prompt = content

        logger.debug(f"len(image_urls)={len(image_urls)}, prompt_len={len(prompt) if prompt else 0}")

        if not prompt:
            return JSONResponse(status_code=400, content={"error": "Prompt is required"})

        logger.info(f"Processing request with {len(image_urls)} image(s) and a prompt.")

        config_kwargs = {
            "max_new_tokens": request.max_completion_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "top_k": request.top_k,
            "repetition_penalty": request.repetition_penalty,
            "presence_penalty": request.presence_penalty,
            "frequency_penalty": request.frequency_penalty,
            "do_sample": request.do_sample,
        }
        config = ov_genai.GenerationConfig(
            **{k: v for k, v in config_kwargs.items() if v is not None}
        )

        if ModelNames.PHI in settings.VLM_MODEL_NAME.lower():
            logger.info("Using phi-3.5-vision model for processing.")
            if len(image_urls) > 0:
                images, image_tensors = await load_images(image_urls)
                placeholder = "".join([f"<|image_{i+1}|>\n" for i in range(len(images))])
                messages = [{"role": "user", "content": placeholder + prompt}]
                formatted_prompt = processor.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                inputs = processor(formatted_prompt, images, return_tensors="pt")
            else:
                formatted_messages = []
                for message in request.messages:
                    if isinstance(message.content, str):
                        formatted_messages.append({"role": message.role, "content": message.content})
                    else:
                        for content in message.content:
                            if isinstance(content, MessageContentText):
                                formatted_messages.append({"role": message.role, "content": content.text})
                formatted_prompt = processor.tokenizer.apply_chat_template(
                    formatted_messages, tokenize=False, add_generation_prompt=True
                )
                inputs = processor(formatted_prompt, return_tensors="pt")

            streamer = TextIteratorStreamer(
                processor, skip_special_tokens=True, skip_prompt=True,
                clean_up_tokenization_spaces=False,
            )
            generation_kwargs = dict(
                **inputs, streamer=streamer,
                max_new_tokens=request.max_completion_tokens,
                top_p=request.top_p, top_k=request.top_k,
                do_sample=request.do_sample, temperature=request.temperature,
                eos_token_id=processor.tokenizer.eos_token_id,
            )
            thread = Thread(target=safe_generate, args=(pipe, generation_kwargs, streamer))
            thread.daemon = True
            thread.start()
            buffer = ""
            for new_text in streamer:
                buffer += new_text
            wait_for_generation_thread(thread)
            return ChatCompletionResponse(
                id=str(uuid.uuid4()), object="chat.completion", created=int(time.time()),
                model=settings.VLM_MODEL_NAME,
                choices=[ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionDelta(role="assistant", content=str(buffer)),
                    finish_reason="stop",
                )],
            )

        elif ModelNames.QWEN in settings.VLM_MODEL_NAME.lower():
            logger.info(f"Using {ModelNames.QWEN} model for processing.")
            if processor.chat_template is None:
                tok = AutoTokenizer.from_pretrained(model_dir)
                processor.chat_template = tok.chat_template

            if len(image_urls) > 0:
                logger.info("Processing as image + text prompt.")
                messages = [
                    {
                        "role": "user",
                        "content": [{"type": "image", "image": img} for img in image_urls]
                        + [{"type": "text", "text": prompt}],
                    }
                ]
                text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = processor(
                    text=[text], images=image_inputs, videos=video_inputs,
                    padding=True, return_tensors="pt",
                )
            else:
                logger.info("Processing as text-only prompt.")
                formatted_messages = []
                for message in request.messages:
                    if isinstance(message.content, str):
                        formatted_messages.append({"role": message.role, "content": message.content})
                    else:
                        for content in message.content:
                            if isinstance(content, MessageContentText):
                                formatted_messages.append({"role": message.role, "content": content.text})
                text = processor.apply_chat_template(
                    formatted_messages, tokenize=False, add_generation_prompt=True
                )
                inputs = processor(text=[text], padding=True, return_tensors="pt")

            streamer = TextIteratorStreamer(
                processor, skip_special_tokens=True, skip_prompt=True,
                clean_up_tokenization_spaces=False,
            )
            generation_kwargs = dict(
                **inputs, streamer=streamer,
                max_new_tokens=request.max_completion_tokens,
                top_p=request.top_p, top_k=request.top_k,
                do_sample=request.do_sample, temperature=request.temperature,
                eos_token_id=processor.tokenizer.eos_token_id,
            )
            thread = Thread(target=safe_generate, args=(pipe, generation_kwargs, streamer))
            thread.daemon = True
            thread.start()
            buffer = ""
            for new_text in streamer:
                buffer += new_text
            wait_for_generation_thread(thread)
            return ChatCompletionResponse(
                id=str(uuid.uuid4()), object="chat.completion", created=int(time.time()),
                model=settings.VLM_MODEL_NAME,
                choices=[ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionDelta(role="assistant", content=str(buffer)),
                    finish_reason="stop",
                )],
            )

        else:
            logger.info("Using default ov_genai pipeline for processing.")
            if len(image_urls) == 0:
                if not prompt or not prompt.strip():
                    raise ValueError("Invalid prompt provided.")
                output = pipe.generate(prompt, generation_config=config)
            else:
                images, image_tensors = await load_images(image_urls)
                output = pipe.generate(prompt, images=image_tensors, generation_config=config)

            logger.info("Chat completion request processed successfully.")
            return ChatCompletionResponse(
                id=str(uuid.uuid4()), object="chat.completion", created=int(time.time()),
                model=settings.VLM_MODEL_NAME,
                choices=[ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionDelta(role="assistant", content=str(output)),
                    finish_reason="stop",
                )],
            )

    except ValueError as e:
        logger.error(f"{ErrorMessages.CHAT_COMPLETION_ERROR}: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error(f"{ErrorMessages.CHAT_COMPLETION_ERROR}: {e}")
        if ErrorMessages.GPU_OOM_ERROR_MESSAGE in str(e):
            restart_server()
        return JSONResponse(
            status_code=500,
            content={"error": f"{ErrorMessages.CHAT_COMPLETION_ERROR}: {e}"},
        )
    finally:
        cleanup_pipeline_state()


@app.get("/health")
async def health_check():
    """
    Perform a health check for the application.

    Returns:
        JSONResponse: A JSON response indicating the health status of the application.
    """
    if model_ready:
        logger.debug("Model is ready. Returning healthy status.")
        return JSONResponse(status_code=200, content={"status": "healthy"})
    else:
        logger.debug("Model is not ready. Returning unhealthy status.")
        return JSONResponse(status_code=503, content={"status": "model not ready"})
