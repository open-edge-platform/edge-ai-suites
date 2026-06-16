from abc import ABC, abstractmethod

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