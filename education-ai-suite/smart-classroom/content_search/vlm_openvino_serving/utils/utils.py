# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import base64
import os
import random
from io import BytesIO
from pathlib import Path
from typing import Dict, List

import numpy as np
import openvino as ov
import torch
import yaml
from openvino_tokenizers import convert_tokenizer
from optimum.exporters.openvino.utils import save_preprocessors
from optimum.intel import (
    OVModelForCausalLM,
    OVModelForFeatureExtraction,
    OVModelForSequenceClassification,
    OVModelForVisualCausalLM,
)
from optimum.utils.save_utils import maybe_load_preprocessors
from PIL import Image
from utils.common import ErrorMessages, logger, settings
from transformers import AutoTokenizer


def convert_model(
    model_id: str, cache_dir: str, model_type: str = "vlm", weight_format: str = "int4"
):
    """
    Converts a specified model to OpenVINO format and saves it to the cache directory.

    Args:
        model_id (str): The identifier of the model to be converted.
        cache_dir (str): The directory where the converted model will be saved.
        model_type (str): The type of the model. It can be "embedding", "reranker", "llm", or "vlm".
        weight_format (str): The format of the model weights. Used for specific model types like "llm" and "vlm".
    Returns:
        None

    Raises:
        ValueError: If the model_type is not one of "embedding", "reranker", "llm", or "vlm".

    Notes:
        - If the model has already been converted and exists in the cache directory, the conversion process is skipped.
        - The function uses the Hugging Face `AutoTokenizer` to load and save the tokenizer.
        - The function uses OpenVINO's `convert_tokenizer` and `save_model` to convert and save the tokenizer.
        - Depending on the model_type, the function uses different OpenVINO model classes to convert and save the model:
            - "embedding": Uses `OVModelForFeatureExtraction`.
            - "reranker": Uses `OVModelForSequenceClassification`.
            - "llm": Uses `OVModelForCausalLM`.
            - "vlm": Uses `OVModelForVisualCausalLM`.
    """
    try:
        logger.debug(f"cache_ddir: {cache_dir}")
        if is_model_ready(Path(cache_dir)):
            logger.info(f"Optimized {model_id} exist in {cache_dir}. Skip process...")
        else:
            logger.info(f"Converting {model_id} model to OpenVINO format...")
            hf_tokenizer = AutoTokenizer.from_pretrained(model_id)
            hf_tokenizer.save_pretrained(cache_dir)
            ov_tokenizer = convert_tokenizer(hf_tokenizer, add_special_tokens=False)
            ov.save_model(ov_tokenizer, f"{cache_dir}/openvino_tokenizer.xml")

            if model_type == "embedding":
                embedding_model = OVModelForFeatureExtraction.from_pretrained(
                    model_id, export=True
                )
                embedding_model.save_pretrained(cache_dir)
            elif model_type == "reranker":
                reranker_model = OVModelForSequenceClassification.from_pretrained(
                    model_id, export=True
                )
                reranker_model.save_pretrained(cache_dir)
            elif model_type == "llm":
                llm_model = OVModelForCausalLM.from_pretrained(
                    model_id, export=True, weight_format=weight_format
                )
                llm_model.save_pretrained(cache_dir)
            elif model_type == "vlm":
                vlm_model = OVModelForVisualCausalLM.from_pretrained(
                    model_id, export=True, weight_format=weight_format
                )
                vlm_model.save_pretrained(cache_dir)
                preprocessors = maybe_load_preprocessors(model_id)
                save_preprocessors(preprocessors, vlm_model.config, cache_dir, True)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
    except Exception as e:
        logger.error(f"Error occurred during model conversion: {e}")
        raise RuntimeError(f"Error occurred during model conversion: {e}")


async def load_images(image_urls_or_files: List[str]):
    """
    Load images from base64 data URLs or local file paths.

    Args:
        image_urls_or_files (List[str]): A list of base64 data URLs or file paths.

    Returns:
        Tuple[List[Image.Image], List[ov.Tensor]]: PIL images and OpenVINO tensors.
    """
    images = []
    image_tensors = []
    for source in image_urls_or_files:
        try:
            if str(source).startswith("data:image/"):
                # base64 data URL: data:image/<mime>;base64,<data>
                decoded = base64.b64decode(source.split(",", 1)[1])
                image = Image.open(BytesIO(decoded)).convert("RGB")
            else:
                image = Image.open(source).convert("RGB")
            image_data = (
                np.array(image.getdata())
                .reshape(1, image.size[1], image.size[0], 3)
                .astype(np.byte)
            )
            images.append(image)
            image_tensors.append(ov.Tensor(image_data))
        except base64.binascii.Error as e:
            raise ValueError(f"Invalid base64 image data: {e}")
        except Exception as e:
            raise RuntimeError(f"{ErrorMessages.LOAD_IMAGE_ERROR}: {e}")
    return images, image_tensors



def is_model_ready(model_dir: Path) -> bool:
    """
    Check if the model is ready by verifying the existence of the OpenVINO model files.

    Args:
        model_dir (Path): The directory where the model is stored.

    Returns:
        bool: True if the model files exist, False otherwise.
    """
    if not model_dir.exists():
        return False
    import re
    pattern = re.compile(r"(.*)?openvino(.*)?_model(.*)?.xml$")
    return any(pattern.search(p.name) for p in model_dir.rglob("*.xml"))


def load_model_config(
    model_name: str, config_path: Path = Path(__file__).resolve().parent.parent / "config" / "model_config.yaml"
) -> Dict:
    """
    Load the configuration for a specific model from a YAML file.

    Args:
        model_name (str): The name of the model.
        config_path (Path): Path to the configuration file.

    Returns:
        dict: The configuration for the specified model.

    Raises:
        RuntimeError: If an error occurs while loading or parsing the configuration.
    """
    try:
        with open(config_path, "r") as config_file:
            configs = yaml.safe_load(config_file)
        config = configs.get(model_name.lower(), {})
        logger.info(f"Loaded configuration for model '{model_name}': {config}")
        return config
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise RuntimeError(f"Error parsing YAML configuration: {e}")
    except Exception as e:
        logger.error(f"Error loading model configuration: {e}")
        raise RuntimeError(f"Error loading model configuration: {e}")


def setup_seed(seed: int):
    """
    Set up the random seed for reproducibility.

    Args:
        seed (int): The seed value to use.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    logger.info(f"Random seed set to: {seed}")



