# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from ..services import (
    process_embeddings
)
from ..logger import logger
from http import HTTPStatus
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["embedding"])

class EmbeddingRequest(BaseModel):
    """
    Input payload for embedding creation.
    Parameters:
      - image_data: Base64-encoded string representing the image to be embedded.
      - metadata: Optional dictionary containing additional information about the image (e.g., image height, width, caption text etc...).
    """

    image_data: str
    metadata: dict = Field(default_factory=dict)


def _validate_request_payload(request: EmbeddingRequest) -> None:
    """Perform lightweight request validation before service invocation."""

    if not request.image_data or not request.image_data.strip():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Input image data is required and cannot be empty.",
        )

    if not isinstance(request.metadata, dict):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Metadata must be a valid JSON object.",
        )

@router.post("/embeddings",
    summary="Create and store an embedding from image data and metadata.",
    response_model=dict
)
async def process_embedding(request: EmbeddingRequest):
    """
    Endpoint to handle embedding requests and store them in the VDMS vector store.
    """

    _validate_request_payload(request)

    try:
        embedding_id = await process_embeddings(request.image_data, request.metadata)
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process embedding")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to process embedding.",
        ) from exc

    return {
        "status": "success",
        "message": "Embedding processed and stored successfully.",
        "id": embedding_id,
    }