from abc import ABC, abstractmethod
from typing import List, Tuple

class BaseOCR(ABC):
    def __init__(self, lang="en", use_angle_cls=True, device="CPU"):
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.device = device

    @abstractmethod
    def ocr(self, file_path: str):
        pass

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        pass

    @abstractmethod
    def extract_text_with_scores(self, file_path) -> Tuple[str, List[float]]:
        """Return (text, per_line_confidence_scores).

        Used by callers (e.g. the content-OCR worker) that need to gate on
        recognition confidence. ``scores`` has one entry per text line in
        ``text``; an empty list means no text was recognized.
        """
        pass