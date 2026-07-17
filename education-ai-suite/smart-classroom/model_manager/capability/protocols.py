from pathlib import Path
from typing import Any, Dict, Iterator, List, Protocol, Union, runtime_checkable

# Result type aliases mirroring the shapes returned by the existing
# capability implementations (components/asr, components/ocr, components/llm).
# ASR backends return either a plain transcript string or a segments dict
# (see components/asr/openai/whisper.py -> Dict[str, Any]).
AsrSegments = Union[str, Dict[str, Any]]
# OCR backends return extracted text (extract_text -> str) or structured
# detections (ocr -> List[List]) (see components/ocr/*/*_ocr_processor.py).
OcrResult = Union[str, List[List]]


@runtime_checkable
class TextGen(Protocol):
    def generate(self, prompt: str, *, stream: bool = True,
                 max_new_tokens: int | None = None,
                 temperature: float | None = None) -> Iterator[str]: ...


@runtime_checkable
class Ocr(Protocol):
    def extract(self, image: Union[bytes, Path]) -> OcrResult: ...


@runtime_checkable
class Asr(Protocol):
    def transcribe(self, audio_chunk: Union[Path, bytes]) -> AsrSegments: ...