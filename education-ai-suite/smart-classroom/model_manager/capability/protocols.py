from pathlib import Path
from typing import Any, Dict, Iterator, List, Protocol, Union, runtime_checkable


AsrSegments = Union[str, Dict[str, Any]]

OcrResult = Union[str, List[List]]


@runtime_checkable
class TextGen(Protocol):
    def generate(self, prompt: str, *, images: list | None = None,
                 stream: bool = True,
                 max_new_tokens: int | None = None,
                 temperature: float | None = None) -> Iterator[str]: ...


@runtime_checkable
class Ocr(Protocol):
    def extract(self, image: Union[bytes, Path]) -> OcrResult: ...


@runtime_checkable
class Asr(Protocol):
    def transcribe(self, audio_chunk: Union[Path, bytes]) -> AsrSegments: ...