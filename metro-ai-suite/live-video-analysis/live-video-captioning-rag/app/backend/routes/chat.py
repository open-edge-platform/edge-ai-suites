# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from ..services import (
    process_query,
    build_chain,
)
from ..logger import logger
from http import HTTPStatus
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api", tags = ["chat"])


class ChatRequest(BaseModel):
    '''
    Pydantic model for validating incoming chat requests. It ensures that the request contains a non-empty 'input' field, which represents the user's query to be processed by the LLM.
    '''
    input: str


@router.post("/chat",
    summary="Handle chat queries and generate responses using the LLM.",
    response_model = dict
)
async def query_chat(request: ChatRequest):
    """
    Endpoint to handle chat queries and generate responses using the LLM.
    """

    if not request.input or request.input == "":
        raise HTTPException(
            status_code = HTTPStatus.UNPROCESSABLE_ENTITY,
            detail = "Input question is required and cannot be empty."
        )

    rag_chain = build_chain()

    return StreamingResponse(
        process_query(rag_chain, request.input),
        media_type = "text/event-stream"
    )