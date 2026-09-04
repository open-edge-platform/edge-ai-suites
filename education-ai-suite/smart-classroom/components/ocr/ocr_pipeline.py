import os
import tempfile
import logging
from datetime import datetime
from typing import Tuple, Optional

from fastapi import UploadFile, HTTPException, status
from utils.ocr_utils.file_detection import is_digital_pdf
from utils.ocr_utils.pdf_utils import pdf_to_images
from constants.ocr_constant import (
    SUPPORTED_PDF_EXTENSIONS,
    SUPPORTED_OCR_EXTENSIONS,
    CODE_OCR_SUCCESS, MSG_OCR_SUCCESS, MSG_OCR_FAILURE,
    OCRStatus,
    ERR_NO_FILE_PROVIDED, ERR_UNSUPPORTED_PDF_TYPE, ERR_UNSUPPORTED_OCR_TYPE,
    ERR_ANALYZING_DOCUMENT, ERR_PROCESSING_DOCUMENT
)
from dto.ocr_dto import OCRResponse
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
from utils.session_paths import SessionPaths
logger = logging.getLogger(__name__)


def _get_ocr_capability():
    """Resolve the OCR capability from the ModelManager hub.
    """
    from model_manager import ModelManager

    return ModelManager.instance().ocr()


def create_ocr_response(
    ocr_status: OCRStatus,
    input_file: str,
    output_file: str = None,
    text: str = None
) -> OCRResponse:
    data = {
        "status": ocr_status.value,
        "input_file": input_file
    }
    if ocr_status == OCRStatus.SUCCESS:
        if text is not None:
            data["text"] = text
        if output_file:
            data["result_file"] = output_file.replace("\\", "/")
        message = MSG_OCR_SUCCESS
    else:
        message = MSG_OCR_FAILURE
    return OCRResponse(
        code=CODE_OCR_SUCCESS,
        data=data,
        message=message,
        timestamp=int(datetime.utcnow().timestamp())
    )


def validate_file_extension(filename: str, allowed_extensions: list) -> Tuple[bool, str]:
    file_ext = os.path.splitext(filename)[1].lower()
    return file_ext in allowed_extensions, file_ext


def save_temp_file(file_content: bytes, prefix: str, filename: str) -> str:
    # mkstemp, not a fixed <prefix>_<filename> path: concurrent requests for the
    # same filename would otherwise write over each other's temp file.
    suffix = os.path.splitext(os.path.basename(filename))[1]
    fd, temp_path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=suffix)

    with os.fdopen(fd, "wb") as f:
        f.write(file_content)

    return temp_path

def cleanup_temp_file(temp_path: str):
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup temp file: {cleanup_error}")


def ocr_detect_file(file: UploadFile) -> OCRResponse:
  
    temp_path = None
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERR_NO_FILE_PROVIDED
            )
        
        is_valid, file_ext = validate_file_extension(file.filename, SUPPORTED_PDF_EXTENSIONS)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERR_UNSUPPORTED_PDF_TYPE
            )
        content = file.file.read()
        temp_path = save_temp_file(content, "ocr_detect", file.filename)
        
        is_digital, message = is_digital_pdf(temp_path)
        logger.info(f"OCR detect-file: {file.filename} -> is_digital={is_digital}")
        
        return OCRResponse(
            code=200,
            data={"is_digital": is_digital},
            message=message,
            timestamp=str(int(datetime.utcnow().timestamp()))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OCR detect-file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERR_ANALYZING_DOCUMENT.format(str(e))
        )
    finally:
        cleanup_temp_file(temp_path)


def ocr_extract_text(file: UploadFile, session_id: Optional[str] = None) -> OCRResponse:
    """Extract text from an uploaded document.

    The text is always returned in ``data["text"]``. It is additionally written
    to ``<session>/ocr_result.txt`` only when the caller supplies a real
    ``X-Session-ID``; callers that just want the text (content_search ingestion)
    omit it so no session folder is created for them.
    """
    temp_path = None
    try:
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_NO_FILE_PROVIDED)
        
        is_valid, file_ext = validate_file_extension(file.filename, SUPPORTED_OCR_EXTENSIONS)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_UNSUPPORTED_OCR_TYPE)

        content = file.file.read()
        temp_path = save_temp_file(content, "ocr_extract", file.filename)

        from utils.config_loader import config as app_config
        ocr = _get_ocr_capability()
        logger.info(f"Using {app_config.models.ocr.provider.upper()} model on {app_config.models.ocr.device} (lang={app_config.app.language})")

        input_file = file.filename
        full_text = []
        is_pdf_file = file.filename.lower().endswith('.pdf')
        if is_pdf_file:
            logger.info("Detected PDF. Converting to images...")
            images = pdf_to_images(temp_path, dpi=300)
            for img in images:
                full_text.append(ocr.extract_text(img))
        else:
            full_text.append(ocr.extract_text(temp_path))

        combined_text = "\n".join(full_text)

        result_file = save_output(combined_text, session_id, "ocr_result.txt") if session_id else None

        success = result_file is None or os.path.exists(result_file)

        if success:
            logger.info(f"OCR extract-text SUCCESS: {file.filename} -> {result_file or 'response only'}")
            return create_ocr_response(OCRStatus.SUCCESS, input_file, result_file, combined_text)
        else:
            logger.error(f"OCR extract-text FAILURE: {file.filename}")
            return create_ocr_response(OCRStatus.FAILURE, input_file)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OCR extract-text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERR_PROCESSING_DOCUMENT.format(str(e))
        )
    finally:
        cleanup_temp_file(temp_path)

def save_output(text: str, session_id: str, filename: str = "ocr_result.txt") -> str:
    output_path = str(SessionPaths.raw_dir(session_id) / filename)
    StorageManager.save(output_path, text, append=False)
    logger.info(f"OCR result saved to: {output_path}")
    return output_path

