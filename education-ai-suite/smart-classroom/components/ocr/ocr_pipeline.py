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
    CODE_OCR_SUCCESS, MSG_OCR_SUCCESS, MSG_OCR_FAILURE,
    OCRStatus,
    ERR_NO_FILE_PROVIDED, ERR_UNSUPPORTED_PDF_TYPE,
    ERR_MISSING_SESSION_ID, ERR_ANALYZING_DOCUMENT, ERR_PROCESSING_DOCUMENT
)
from dto.ocr_dto import OCRResponse
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
logger = logging.getLogger(__name__)


def create_ocr_response(
    ocr_status: OCRStatus,
    input_file: str,
    output_file: str = None
) -> OCRResponse:  
    data = {
        "status": ocr_status.value,
        "input_file": input_file
    }  
    if ocr_status == OCRStatus.SUCCESS and output_file:
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
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{prefix}_{filename}")
    
    with open(temp_path, "wb") as f:
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


def ocr_extract_text(file: UploadFile, session_id: str) -> OCRResponse:
    temp_path = None
    try:
        if not session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=ERR_MISSING_SESSION_ID)
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_NO_FILE_PROVIDED)
        
        is_valid, file_ext = validate_file_extension(file.filename, SUPPORTED_PDF_EXTENSIONS)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_UNSUPPORTED_PDF_TYPE)
        
        content = file.file.read()
        temp_path = save_temp_file(content, f"ocr_extract_{session_id}", file.filename)
        
        from components.ocr_component import OCRComponent
        from utils.config_loader import config as app_config
        ocr = OCRComponent(
            session_id=session_id,
            provider=app_config.models.ocr.provider,
            lang=app_config.app.language,
            device=app_config.models.ocr.device,
        )
        logger.info(f"Using {app_config.models.ocr.provider.upper()} model on {app_config.models.ocr.device} (lang={app_config.app.language})")

        input_file = file.filename
        full_text = []
        is_pdf_file = file.filename.lower().endswith('.pdf')
        if is_pdf_file:
            logger.info("Detected PDF. Converting to images...")
            images = pdf_to_images(temp_path, dpi=300)
            for img in images:
                text = ocr.ocr_model.extract_text(img)
                full_text.append(text)
        else:
            full_text.append(ocr.ocr_model.extract_text(temp_path))

        combined_text = "\n".join(full_text)

        result_file = save_output(combined_text, session_id, "ocr_result.txt")

        success = result_file is not None and os.path.exists(result_file)

        if success:
            logger.info(f"OCR extract-text SUCCESS: {file.filename} -> {result_file}")
            return create_ocr_response(OCRStatus.SUCCESS, input_file, result_file)
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
    project_config = RuntimeConfig.get_section("Project")
    project_path = os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            session_id
        )
    output_path = os.path.join(project_path, filename)
    StorageManager.save(output_path, text, append=False)
    logger.info(f"OCR result saved to: {output_path}")
    return output_path

