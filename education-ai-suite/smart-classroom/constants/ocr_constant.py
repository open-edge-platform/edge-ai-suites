from enum import Enum


# OCR Status Enum
class OCRStatus(Enum):
    """Enum for OCR processing status."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


# Supported file extensions
SUPPORTED_PDF_EXTENSIONS = ['.pdf']

# Default OCR configuration
DEFAULT_PROVIDER = "openvino"
DEFAULT_LANG = "en"
DEFAULT_DEVICE = "CPU"
DEFAULT_USE_ANGLE_CLS = True

# Supported providers
SUPPORTED_PROVIDERS = ["native", "openvino"]

# Supported languages
SUPPORTED_LANGUAGES = ["en", "ch"]

# Response code
CODE_OCR_SUCCESS = 200

# Response messages
MSG_OCR_SUCCESS = "Handwritten document successfully converted to text"
MSG_OCR_FAILURE = "Error occurred while processing the file"

# Error detail messages
ERR_NO_FILE_PROVIDED = "No file provided"
ERR_UNSUPPORTED_PDF_TYPE = f"Unsupported file type. Allowed: {SUPPORTED_PDF_EXTENSIONS}"
ERR_MISSING_SESSION_ID = "Missing required header: X-Session-ID"
ERR_ANALYZING_DOCUMENT = "Error analyzing document: {}"
ERR_PROCESSING_DOCUMENT = "Error processing document: {}"
ERR_FAILED_TO_ANALYZE = "Failed to analyze document: {}"

# File detection messages
MSG_DIGITAL_PDF = "Document contains embedded text ({}/{} pages)"
MSG_HANDWRITTEN_PDF = "Document appears to be handwritten or scanned (no embedded text found)"
