import fitz
import logging
from typing import Tuple
from constants.ocr_constant import MSG_DIGITAL_PDF, MSG_HANDWRITTEN_PDF, ERR_FAILED_TO_ANALYZE

logger = logging.getLogger(__name__)


def is_digital_pdf(file_path: str) -> Tuple[bool, str]:
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        pages_with_text = 0
        
        for page in doc:
            text = page.get_text().strip()
            if text:
                pages_with_text += 1
        
        doc.close()
        
        is_digital = pages_with_text > 0
        
        if is_digital:
            message = MSG_DIGITAL_PDF.format(pages_with_text, total_pages)
        else:
            message = MSG_HANDWRITTEN_PDF
        
        logger.info(f"File detection for {file_path}: is_digital={is_digital}, {message}")
        return is_digital, message
        
    except Exception as e:
        logger.error(f"Error detecting file type for {file_path}: {e}")
        raise ValueError(ERR_FAILED_TO_ANALYZE.format(str(e)))
