# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
import time
import uuid
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

import openvino_genai as ov_genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_utils.tasks import repeat_every
from providers.vlm_openvino_serving.utils.common import ErrorMessages, logger, settings
from providers.vlm_openvino_serving.utils.data_models import (
    ChatCompletionChoice,
    ChatCompletionDelta,
    ChatCompletionResponse,
    ChatRequest,
    MessageContentImageUrl,
    MessageContentText,
)
from providers.vlm_openvino_serving.utils.utils import (
    convert_model,
    is_model_ready,
    load_images,
    setup_seed,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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
    model_dir = Path(os.getcwd()).parent / "models" / "openvino" / model_dir
    model_dir.mkdir(parents=True, exist_ok=True)
    weight = settings.VLM_COMPRESSION_WEIGHT_FORMAT.lower()
    model_dir = model_dir / weight
    logger.info(f"Model_name: {model_name} \b Compression_Weight_Format: {weight}")

    try:
        if not is_model_ready(model_dir, require_detokenizer=True):
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
        ov_config = settings.get_ov_config_dict()
        logger.debug(f"Using OpenVINO configuration: {ov_config}")
        pipe = ov_genai.VLMPipeline(
            model_dir, device=settings.VLM_DEVICE.upper(), **ov_config
        )
        processor = None
        model_ready = is_model_ready(model_dir, require_detokenizer=True)
        logger.debug("Model is ready")
    except Exception as e:
        logger.error(f"Error initializing the model: {e}")
        raise RuntimeError(f"Error initializing the model: {e}")


# Initialize the model to create global objects of processor, model, model_ready
initialize_model()


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

        logger.info("Using ov_genai VLMPipeline for processing.")
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
