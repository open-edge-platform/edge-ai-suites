# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from ..config import (
    LLM_MODEL_ID,
)
from ..llm import initialize_llm
from ..logger import logger
from .embedding import CaptionEmbeddings
from .prompt import get_prompt_template
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import json
import asyncio


llm = initialize_llm()
template = get_prompt_template(LLM_MODEL_ID)
prompt = ChatPromptTemplate.from_template(template)

caption_embeddings = CaptionEmbeddings()


def _is_vdms_retryable_error(exc: Exception) -> bool:
    """Identify likely transient VDMS/transport failures safe to retry once."""
    err = str(exc).lower()
    retry_markers = (
        "vdms",
        "connection",
        "timed out",
        "timeout",
        "reset by peer",
        "broken pipe",
        "eof",
        "refused",
        "transport",
        "socket",
    )
    return any(marker in err for marker in retry_markers)

async def process_embeddings(image_data: str, metadata: dict):
    """
    Process incoming embedding requests by adding the image-caption pair to the VDMS vector store.
    """
    # Offload synchronous network and vector DB writes to a thread to avoid
    # blocking the event loop in async API handlers.
    ids = await asyncio.to_thread(
        caption_embeddings.process_embeddings,
        image_data,
        metadata,
    )
    return ids

def default_context(docs):
    """
    Default context function that concatenates retrieved documents into a single string.
    This function is used when no retriever is provided to the chain, allowing for a simple context construction by joining the content of the retrieved documents.
    """
    return ""


def format_docs(docs):
    """Concatenate retrieved document text for prompt context."""
    return "\n\n".join(doc.page_content for doc in docs)


def build_chain():
    """
    Build a LangChain chain that combines the retriever, prompt template, and LLM for processing queries.
    """
    retriever = caption_embeddings.get_retriever()

    if retriever:
        chain = (
            RunnableParallel(
                {
                    "source_documents": retriever,
                    "question": RunnablePassthrough(),
                }
            )
            .assign(context=lambda x: format_docs(x["source_documents"]))
            .assign(answer=prompt | llm | StrOutputParser())
        )
    else:
        chain = (
            RunnableParallel(
                {
                    "question": RunnablePassthrough(),
                }
            )
            .assign(context=lambda _: "")
            .assign(answer=prompt | llm | StrOutputParser())
        )

    return chain


async def process_query(chain=None, query: str = ""):
    """
    Process a query by running it through the LangChain chain, yielding results as they are generated.
    This function handles the execution of the chain and yields intermediate answers and source documents in a format suitable for streaming responses in an API context.
    """
    if chain is None:
        chain = build_chain()

    docs = []
    has_streamed_answer = False

    try:
        async for chunk in chain.astream(query):
            if "source_documents" in chunk and chunk["source_documents"]:
                docs = chunk["source_documents"]

            if "answer" in chunk and chunk["answer"]:
                has_streamed_answer = True
                yield f"data: {chunk['answer']}\n\n"
    except Exception as exc:
        # Retry only if no partial answer was sent to avoid duplicate streamed tokens.
        if has_streamed_answer or not _is_vdms_retryable_error(exc):
            raise

        logger.warning("Query failed due to VDMS/retrieval error; reinitializing and retrying once. Error: %s", exc)
        caption_embeddings.reconnect_vdms(exc)
        chain = build_chain()
        docs = []

        async for chunk in chain.astream(query):
            if "source_documents" in chunk and chunk["source_documents"]:
                docs = chunk["source_documents"]

            if "answer" in chunk and chunk["answer"]:
                yield f"data: {chunk['answer']}\n\n"

    # Example of sources data: [{'metadata': {'frame_data': 'base64_encoded', 'frame_format': 'BGRA', 'frame_height': 1080, 'frame_id': 11, 'frame_width': 1920}, 'preview': '<caption_text>'}, {'metadata': {'frame_data': 'base64_encoded', 'frame_format': 'BGRA', 'frame_height': 1080, 'frame_id': 10, 'frame_width': 1920}, 'preview': '<caption_text>'}, {'metadata': {'frame_data': 'base64_encoded', 'frame_format': 'BGRA', 'frame_height': 1080, 'frame_id': 4, 'frame_width': 1920}, 'preview': '<caption_text>'}]
    sources = [
        {
            "metadata": d.metadata,
            # Optional: include a preview/snippet for UX.
            "preview": d.page_content[:200],
        }
        for d in docs
    ]

    # Done marker
    yield "event: frame\n"
    yield f"data: {json.dumps(sources)}\n\n"
