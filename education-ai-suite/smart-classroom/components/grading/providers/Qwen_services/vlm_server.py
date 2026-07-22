"""VLM API Server using Qwen3.5-9B-int8-ov with OpenVINO"""

import numpy as np
import openvino as ov
import openvino_genai as ov_genai
from PIL import Image
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Union
from contextlib import asynccontextmanager
import base64
import io
import sys
import os
import logging
import time
import traceback
import uvicorn
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)7s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_config():
    """Load vlm_service config next to this script; fall back to defaults."""
    defaults = {
        "host": "127.0.0.1",
        "port": 9900,
        "model_name": "Qwen3.5-9B-int8-ov",
        "model_path": "../models/Qwen3.5-9B-int8-ov",
        "device": "GPU.1",
        "cache_dir": "ov_cache",
        "performance_hint": "LATENCY",
        "inference_precision_hint": "f16",
        "max_tokens": 512,
        "temperature": 0.3,
        "max_image_size": 1920,
    }
    config_path = os.path.join(SCRIPT_DIR, "config.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        svc = raw.get("vlm_service", {}) if isinstance(raw, dict) else {}
        if isinstance(svc, dict):
            defaults.update({k: v for k, v in svc.items() if v is not None})
    except FileNotFoundError:
        logger.warning(f"config.yaml not found at {config_path}, using defaults")
    except Exception as e:
        logger.warning(f"Failed to read config.yaml ({e}), using defaults")
    return defaults


CONFIG = _load_config()

MODEL_NAME = CONFIG["model_name"]
# model_path / cache_dir are resolved relative to this script's directory.
MODEL_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, CONFIG["model_path"]))
DEVICE = CONFIG["device"]
HOST = CONFIG["host"]
PORT = int(CONFIG["port"])
CACHE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, CONFIG["cache_dir"]))
PERFORMANCE_HINT = CONFIG["performance_hint"]
INFERENCE_PRECISION_HINT = CONFIG["inference_precision_hint"]
DEFAULT_MAX_TOKENS = int(CONFIG["max_tokens"])
DEFAULT_TEMPERATURE = float(CONFIG["temperature"])
MAX_IMAGE_SIZE = int(CONFIG["max_image_size"])

vlm_pipeline = None
current_device = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_model()
    yield


# FastAPI应用
app = FastAPI(
    title="VLM API Server",
    description="OpenAI-compatible API for Qwen3.5-9B-int8-ov",
    version="1.0.0",
    lifespan=lifespan
)


# Pydantic模型定义
class ImageURL(BaseModel):
    url: str


class ContentText(BaseModel):
    type: str = "text"
    text: str


class ContentImage(BaseModel):
    type: str = "image_url"
    image_url: ImageURL


class Message(BaseModel):
    role: str
    content: Union[str, List[Union[ContentText, ContentImage]]]


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_NAME
    messages: List[Message]
    max_completion_tokens: int = Field(default=DEFAULT_MAX_TOKENS, ge=1, le=4096)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Usage


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    model_path: str


def load_model():
    """加载VLM模型"""
    global vlm_pipeline, current_device

    logger.info("=" * 60)
    logger.info("Model Loading")
    logger.info("=" * 60)
    logger.info(f"Model path: {MODEL_PATH}")
    logger.info(f"Target device: {DEVICE}")

    # 检查模型目录
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Model directory not found: {MODEL_PATH}")
        logger.error("Please run download_models.py first")
        sys.exit(1)

    # 检查关键文件
    critical_file = os.path.join(MODEL_PATH, "openvino_language_model.bin")
    if not os.path.exists(critical_file):
        logger.error(f"Model file not found: {critical_file}")
        logger.error("Model download may be incomplete")
        sys.exit(1)

    file_size_gb = os.path.getsize(critical_file) / (1024**3)
    logger.info(f"Model file size: {file_size_gb:.2f} GB")

    ov_cache_dir = CACHE_DIR
    os.makedirs(ov_cache_dir, exist_ok=True)

    ov_config = {
        "CACHE_DIR": ov_cache_dir,
        "PERFORMANCE_HINT": PERFORMANCE_HINT,
        "INFERENCE_PRECISION_HINT": INFERENCE_PRECISION_HINT,
    }

    try:
        logger.info(f"Loading model on {DEVICE}...")
        logger.info(f"Cache directory: {ov_cache_dir}")
        start_time = time.time()

        vlm_pipeline = ov_genai.VLMPipeline(MODEL_PATH, DEVICE, **ov_config)
        current_device = DEVICE

        load_time = time.time() - start_time
        logger.info(f"Model loaded successfully on {DEVICE} ({load_time:.1f}s)")

    except Exception as e:
        if DEVICE == "GPU":
            logger.warning(f"Failed to load on GPU: {e}")
            logger.info("Falling back to CPU...")

            try:
                start_time = time.time()
                vlm_pipeline = ov_genai.VLMPipeline(MODEL_PATH, "CPU")
                current_device = "CPU"
                load_time = time.time() - start_time
                logger.info(f"Model loaded successfully on CPU ({load_time:.1f}s)")
            except Exception as cpu_error:
                logger.error(f"Failed to load on CPU: {cpu_error}")
                traceback.print_exc()
                sys.exit(1)
        else:
            logger.error(f"Failed to load model: {e}")
            traceback.print_exc()
            sys.exit(1)

    logger.info("=" * 60)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    if vlm_pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return HealthResponse(
        status="ok",
        model=MODEL_NAME,
        device=current_device,
        model_path=MODEL_PATH
    )


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    start_time = time.time()

    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        user_message = None
        for msg in reversed(request.messages):
            if msg.role == 'user':
                user_message = msg
                break

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        content = user_message.content
        if isinstance(content, str):
            content = [ContentText(type="text", text=content)]

        prompt_text = ""
        images = []

        for item in content:
            if isinstance(item, ContentText) or (isinstance(item, dict) and item.get('type') == 'text'):
                prompt_text = item.text if isinstance(item, ContentText) else item.get('text', '')
            elif isinstance(item, ContentImage) or (isinstance(item, dict) and item.get('type') == 'image_url'):
                image_url = item.image_url.url if isinstance(item, ContentImage) else item.get('image_url', {}).get('url', '')
                if image_url.startswith('data:image'):
                    try:
                        image_data = image_url.split(',', 1)[1]
                        image_bytes = base64.b64decode(image_data)
                        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

                        if max(image.size) > MAX_IMAGE_SIZE:
                            ratio = MAX_IMAGE_SIZE / max(image.size)
                            new_size = (int(image.width * ratio), int(image.height * ratio))
                            image = image.resize(new_size, Image.Resampling.LANCZOS)
                            logger.info(f"Resized image: {image.size}")

                        images.append(image)
                        logger.debug(f"Decoded image: {image.size}")
                    except Exception as img_error:
                        logger.error(f"Failed to decode image: {img_error}")
                        raise HTTPException(status_code=400, detail=f"Invalid image data: {str(img_error)}")

        if not prompt_text:
            raise HTTPException(status_code=400, detail="No text prompt found")

        prompt_text = prompt_text.strip()

        logger.info(f"Request: prompt={len(prompt_text)} chars, images={len(images)}, max_completion_tokens={request.max_completion_tokens}")

        gen_start = time.time()

        from openvino_genai import GenerationConfig

        gen_config = GenerationConfig()
        gen_config.max_new_tokens = request.max_completion_tokens
        gen_config.do_sample = False

        # Disable Qwen3 thinking mode at the chat-template level (more reliable
        # than the "/no_think" soft switch): apply the template manually with
        # enable_thinking=False so an empty <think></think> block is inserted and
        # the model answers directly, then turn off the pipeline's internal
        # templating. Prepend the image placeholder so the pipeline still
        # positions the image correctly.
        gen_prompt = prompt_text
        try:
            media_tags = "<ov_genai_image_0>" if images else ""
            history = [{"role": "user", "content": media_tags + prompt_text}]
            gen_prompt = vlm_pipeline.get_tokenizer().apply_chat_template(
                history, True, "", None, {"enable_thinking": False}
            )
            gen_config.apply_chat_template = False
        except Exception as tmpl_error:
            logger.warning(f"Manual chat template failed, falling back to raw prompt: {tmpl_error}")
            gen_prompt = prompt_text

        if images:
            image_array = np.array(images[0])
            logger.debug(f"Image array shape: {image_array.shape}")

            image_tensor = ov.Tensor(image_array[None])

            result = vlm_pipeline.generate(
                gen_prompt,
                image=image_tensor,
                generation_config=gen_config
            )
        else:
            result = vlm_pipeline.generate(
                gen_prompt,
                generation_config=gen_config
            )

        response_text = str(result)

        finish_reason = "stop"
        try:
            if hasattr(result, 'finish_reason'):
                finish_reason = str(result.finish_reason)
                logger.info(f"VLM finish_reason: {finish_reason}")
            elif hasattr(result, 'scores'):
                logger.debug(f"Result type: {type(result)}, attributes: {dir(result)}")
        except Exception as e:
            logger.debug(f"Could not get finish_reason: {e}")

        gen_time = time.time() - gen_start
        total_time = time.time() - start_time

        logger.info(f"Response: {len(response_text)} chars, gen_time={gen_time:.2f}s, total_time={total_time:.2f}s")

        if len(response_text) < 50 and request.max_completion_tokens > 100:
            logger.warning(f"Response suspiciously short: {len(response_text)} chars with max_completion_tokens={request.max_completion_tokens}")

        prompt_tokens = max(len(prompt_text) // 2, 1)
        completion_tokens = max(len(response_text) // 2, 1)

        return ChatCompletionResponse(
            id="chatcmpl-" + os.urandom(12).hex(),
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=response_text
                    ),
                    finish_reason=finish_reason
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    print("=" * 60)
    print(f"VLM API Server - {MODEL_NAME}")
    print("=" * 60)
    print(f"Starting server on http://{HOST}:{PORT}")
    print(f"")
    print(f"Endpoints:")
    print(f"  - GET  /health                  (Health check)")
    print(f"  - POST /v1/chat/completions     (OpenAI API)")
    print(f"  - GET  /docs                    (Swagger UI)")
    print(f"  - GET  /redoc                   (ReDoc)")
    print(f"")
    print(f"Press Ctrl+C to stop the server")
    print("=" * 60)

    try:
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
