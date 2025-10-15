import os
import logging
from fastapi import UploadFile, HTTPException
from utils.config_loader import config
from utils.runtime_config_loader import RuntimeConfig

logger = logging.getLogger(__name__)

def save_audio_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    allowed_extensions = [ext.lower() for ext in config.audio_util.allowed_extensions]
    max_file_size_mb = config.audio_util.max_size_mb
    max_file_size_bytes = max_file_size_mb * 1024 * 1024

    project_config = RuntimeConfig.get_section("Project")
    base_storage_path = os.path.join(
        project_config.get("location"),  
        project_config.get("name")      
    )
    project_path = os.path.join(base_storage_path, "audio")
    os.makedirs(project_path, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = bytearray()
    total_read = 0
    chunk_size = config.audio_util.chunk_size 

    while True:
        chunk = file.file.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_file_size_bytes:
            raise HTTPException(status_code=400, detail="File too large")
        contents.extend(chunk)

    file.file.seek(0)

    file_path = os.path.join(project_path, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    logger.info(f"File saved: {file_path}")

    return file.filename, file_path
