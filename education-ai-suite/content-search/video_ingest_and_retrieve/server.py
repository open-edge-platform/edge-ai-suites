# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import re
import logging
import json
from tqdm import tqdm
from pathlib import Path

from pydantic import BaseModel
from typing import Optional, Dict, Union

from minio import Minio
import tempfile

from video_ingest_and_retrieve.indexer import Indexer
from video_ingest_and_retrieve.retriever import ChromaRetriever

logger = logging.getLogger("visual_data_service")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s.%(msecs)03d [%(name)s]: %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)

class RetrievalRequest(BaseModel):
    query: Optional[str] = None
    image_base64: Optional[str] = None
    filter: Optional[Dict] = None
    max_num_results: int = 10

class IngestMinioDirRequest(BaseModel):
    bucket_name: str
    folder_path: str
    frame_extract_interval: int = 15
    do_detect_and_crop: bool = False

class IngestMinioFileRequest(BaseModel):
    bucket_name: str
    file_path: str
    meta: dict = {}
    frame_extract_interval: int = 15
    do_detect_and_crop: bool = False

app = FastAPI()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

VISUAL_DATA_DB_COLLECTION_NAME = os.getenv("VISUAL_DATA_DB_COLLECTION_NAME", "visual_data")

indexer = Indexer(collection_name=VISUAL_DATA_DB_COLLECTION_NAME)

retriever = ChromaRetriever(collection_name=VISUAL_DATA_DB_COLLECTION_NAME)

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)


@app.get("/v1/dataprep/health")
def health():
    """
    Health check endpoint.
    """
    try:
        # Perform a simple health check
        return JSONResponse(content={"status": "healthy"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

    
@app.get("/v1/dataprep/info")
def info():
    """
    Get current status info.
    """
    try:
        status_info = {
            "model_name": indexer.model_name,
        }
        return JSONResponse(content=status_info, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status info: {str(e)}")

@app.post("/v1/dataprep/ingest")
async def ingest(request: Union[IngestMinioDirRequest, IngestMinioFileRequest] = Body(...)):
    """
    Ingest files from a directory or a single file.

    Args:
        request (Union[IngestMinioDirRequest, IngestMinioFileRequest, IngestFileURLRequest]): The request body containing file_dir, file_path, metadata, frame_extract_interval, and do_detect_and_crop.

    Returns:
        JSONResponse: A response indicating success or failure.
    """   
    if isinstance(request, IngestMinioDirRequest):
        logger.info(f"Received IngestMinioDirRequest: {request}")
        return await ingest_minio_dir(request)
    elif isinstance(request, IngestMinioFileRequest):
        logger.info(f"Received IngestMinioFileRequest: {request}")
        return await ingest_minio_file(request)
    else:
        raise HTTPException(status_code=422, detail="Invalid request type. Provide either 'bucket_name' for minio, or 'file_url'.")


async def ingest_minio_dir(request: IngestMinioDirRequest = Body(...)):
    """
    Ingest files from a MinIO directory.
    """
    try:
        bucket_name = request.bucket_name
        folder_path = request.folder_path
        frame_extract_interval = request.frame_extract_interval
        do_detect_and_crop = request.do_detect_and_crop

        if not minio_client.bucket_exists(bucket_name):
            raise HTTPException(status_code=404, detail=f"Bucket {bucket_name} not found.")

        objects = minio_client.list_objects(bucket_name, prefix=folder_path, recursive=True)

        proc_files = []
        metas = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for obj in objects:
                if not obj.object_name.lower().endswith(('.jpg', '.png', '.jpeg', '.mp4')):
                    logger.debug(f"Unsupported file type: {obj.object_name}, skipped.")
                    continue

                local_file_path = os.path.join(temp_dir, os.path.basename(obj.object_name))
                minio_client.fget_object(bucket_name, obj.object_name, local_file_path)
                
                meta = {"file_path": f"minio://{bucket_name}/{obj.object_name}"}
                proc_files.append(local_file_path)
                metas.append(meta)

            if not proc_files:
                return JSONResponse(content={"message": "No supported files found in the specified MinIO path."}, status_code=200)

            res = indexer.add_embedding(proc_files, metas, frame_extract_interval=frame_extract_interval, do_detect_and_crop=do_detect_and_crop)

        return JSONResponse(
            content={"message": f"Files from MinIO directory successfully processed. db returns {res}"},
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing files from MinIO: {str(e)}")


async def ingest_minio_file(request: IngestMinioFileRequest = Body(...)):
    """
    Ingest a single file from MinIO.
    """
    try:
        bucket_name = request.bucket_name
        file_path = request.file_path
        meta = request.meta
        frame_extract_interval = request.frame_extract_interval
        do_detect_and_crop = request.do_detect_and_crop

        if not minio_client.bucket_exists(bucket_name):
            raise HTTPException(status_code=404, detail=f"Bucket {bucket_name} not found.")

        with tempfile.TemporaryDirectory() as temp_dir:
            local_file_path = os.path.join(temp_dir, os.path.basename(file_path))
            minio_client.fget_object(bucket_name, file_path, local_file_path)

            meta["file_path"] = f"minio://{bucket_name}/{file_path}"
            res = indexer.add_embedding([local_file_path], [meta], frame_extract_interval=frame_extract_interval, do_detect_and_crop=do_detect_and_crop)

        return JSONResponse(
            content={"message": f"File from MinIO successfully processed. db returns {res}"},
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file from MinIO: {str(e)}")

@app.get("/v1/dataprep/get")
def get_file_info(file_path: str):
    """
    Get file info from db.

    Args:
        file_path (str): The path to the file.

    Returns:
        FileResponse: The requested file info.
    """
    try:
        if not file_path or not isinstance(file_path, str):
            raise HTTPException(status_code=400, detail="Invalid file_path parameter. It must be a non-empty string.")

        # For remote files, we don't check for local existence
        if not (file_path.startswith("minio://") or file_path.startswith("http")):
            raise HTTPException(status_code=404, detail="File not found.")
        
        res, ids = indexer.query_file(file_path)
        
        return JSONResponse(
            content={
                "file_path": file_path,
                "ids_in_db": ids,
            },
            status_code=200,
        )
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions to preserve their status code and message
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")

@app.delete("/v1/dataprep/delete")
def delete_file_in_db(file_path: str):
    """
    Delete file entity in db. Note that the orginal file will NOT be deleted.

    Args:
        file_path (str): The path to the file.

    Returns:
        JSONResponse: A response indicating success or failure.
    """
    try:
        if not file_path or not isinstance(file_path, str):
            raise HTTPException(status_code=400, detail="Invalid file_path parameter. It must be a non-empty string.")

        # For remote files, we don't check for local existence
        if not (file_path.startswith("minio://") or file_path.startswith("http")):
            raise HTTPException(status_code=404, detail="File not found.")
        
        res, ids = indexer.delete_by_file_path(file_path)
        
        return JSONResponse(
            content={
                "message": f"File successfully deleted. db returns: {res}",
                "removed_ids": ids,
            },
            status_code=200,
        )
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions to preserve their status code and message
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@app.delete("/v1/dataprep/delete_all")
def clear_db():
    """
    Clear the database. Note that the orginal file will NOT be deleted.

    Returns:
        JSONResponse: A response indicating success or failure.
    """
    try:
        res, _ = indexer.delete_all()
        return JSONResponse(
            content={
                "message": f"Database successfully cleared. db returns: {res}"
            },
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing database: {str(e)}")


@app.get("/v1/retrieval/health")
def health():
    """
    Health check endpoint.
    """
    try:
        # Perform a simple health check
        return JSONResponse(content={"status": "healthy"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@app.post("/v1/retrieval")
async def retrieval(request: RetrievalRequest):
    """
    Perform a retrieval task using the provided text or base64-encoded image input.

    Args:
        request (RetrievalRequest): The JSON body containing query, image_base64, filter, and max_num_results.

    Returns:
        JSONResponse: A response containing the top-k retrieved results.
    """
    try:
        # Validate input
        if not request.query and not request.image_base64:
            raise HTTPException(status_code=400, detail="Either 'query' or 'image_base64' must be provided.")
        if request.query and request.image_base64:
            raise HTTPException(status_code=400, detail="Provide only one of 'query' or 'image_base64', not both.")
        if not isinstance(request.max_num_results, int) or request.max_num_results <= 0:
            raise HTTPException(status_code=400, detail="Invalid max_num_results. It must be a positive integer.")
        if request.max_num_results > 16384:
            raise HTTPException(status_code=400, detail="Invalid max_num_results. It must be in the range [1, 16384].")

        # Process query or image_base64
        if request.query:
            results = retriever.search(query=request.query, filters=request.filter, top_k=request.max_num_results)
        else:
            try:
                results = retriever.search(image_base64=request.image_base64, filters=request.filter, top_k=request.max_num_results)
            except Exception as e:
                logger.error(f"Error processing image_base64: {e}")
                raise HTTPException(status_code=400, detail=f"Error processing image_base64: {str(e)}")

        # Format results
        ret = []
        if results and results['ids']:
            for i in range(len(results['ids'][0])):
                ret.append({
                    "id": results['ids'][0][i],
                    "distance": results['distances'][0][i],
                    "meta": results['metadatas'][0][i]
                })

        # Return the results
        return JSONResponse(
            content={
                "results": ret
            },
            status_code=200,
        )
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions to preserve their status code and message
        raise http_exc
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=f"Error during retrieval: {str(e)}")

