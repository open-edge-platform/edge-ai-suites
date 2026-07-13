import logging
import tempfile
import threading
import time
import wave
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue
import re
from typing import Callable
from uuid import uuid4

import numpy as np
import sounddevice as sd

from kiosk_core import config
from kiosk_core.analyzer_client import AnalyzerClient
from kiosk_core.models import FileSessionStartRequest, SessionStartRequest
from kiosk_core.rag_client import RagClient
from kiosk_core.tts_client import TtsClient


logger = logging.getLogger(__name__)
_SENTENCE_PATTERN = re.compile(r"^(.+?[.!?,:;](?:[\"')\]]+)?)(?:\s+|$)", re.DOTALL)
# Whisper hallucination tokens to strip from transcripts
_WHISPER_JUNK = re.compile(
    r"\[(?:BLANK_AUDIO|Music|Noise|Applause|Laughter|Silence|Background Music|noise|music)\]",
    re.IGNORECASE,
)

class BaseAudioSession:
    def __init__(
        self,
        request: SessionStartRequest,
        on_complete: Callable[[str], None] | None = None,
    ):
        self.session_id = str(uuid4())
        self.request = request
        self.on_complete = on_complete
        self.client = AnalyzerClient(request.analyzer_url)
        self.rag_client = RagClient(request.rag_url)
        self.tts_client = TtsClient(request.tts_url)
        self.created_at = datetime.now(UTC)
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.status = "created"
        self.end_reason: str | None = None
        self.error: str | None = None
        self.transcript_parts: list[str] = []
        self.response_parts: list[str] = []
        self.tts_audio_segments: list[dict[str, object]] = []
        self.tts_errors: list[str] = []
        self.performance_metrics: dict[str, object] = {}
        self.llm_metrics: dict[str, object] = {}
        self.rag_sources: list[dict[str, object]] = []
        self.stop_requested_at: datetime | None = None

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._audio_queue: Queue[np.ndarray] = Queue()
        self._thread = threading.Thread(target=self._run, name=f"mic-session-{self.session_id}", daemon=True)
        self._speech_started = False
        self._captured_samples = 0
        self._source_kind = "audio"

        self._frame_samples = max(1, int(self.request.sample_rate * config.DEFAULT_BLOCK_DURATION_SECONDS))
        self._frame_duration_seconds = self._frame_samples / self.request.sample_rate
        preroll_frames = max(1, int(config.DEFAULT_PREROLL_SECONDS / self._frame_duration_seconds))
        self._preroll_frames: deque[np.ndarray] = deque(maxlen=preroll_frames)
        self._session_output_dir = Path(__file__).resolve().parent.parent / "generated_audio" / self.session_id
        # Ensure output directory exists
        self._session_output_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        with self._lock:
            if self.status != "created":
                raise ValueError("Session already started")
            self.status = "running"
            self.started_at = datetime.now(UTC)
        self._thread.start()

    def stop(self, reason: str = "stopped_by_api") -> None:
        with self._lock:
            if self.status not in {"running", "stopping"}:
                raise ValueError(f"Session is not running: {self.status}")
            self.status = "stopping"
            self.end_reason = reason
            self.stop_requested_at = datetime.now(UTC)
        self._stop_event.set()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            transcript = " ".join(part for part in self.transcript_parts if part).strip()
            response_text = "".join(self.response_parts).strip()
            return {
                "session_id": self.session_id,
                "source_kind": self._source_kind,
                "status": self.status,
                "created_at": self.created_at.isoformat(),
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "stop_requested_at": self.stop_requested_at.isoformat() if self.stop_requested_at else None,
                "end_reason": self.end_reason,
                "error": self.error,
                "speech_started": self._speech_started,
                "captured_audio_seconds": round(self._captured_samples / self.request.sample_rate, 3),
                "transcript": transcript,
                "partial_transcript": transcript,
                "transcript_parts": list(self.transcript_parts),
                "response": response_text,
                "response_parts": list(self.response_parts),
                "tts_audio_segments": [dict(segment) for segment in self.tts_audio_segments],
                "tts_errors": list(self.tts_errors),
                "performance_metrics": dict(self.performance_metrics),
                "llm_metrics": dict(self.llm_metrics),
                "sources": list(self.rag_sources),
            }

    def _run(self) -> None:
        raise NotImplementedError

    def _process_frame_stream(self, frame_iterator) -> tuple[str, str | None]:
        chunk_frames: list[np.ndarray] = []
        silence_run_seconds = 0.0
        final_status = "completed"
        end_reason = self.end_reason or "completed"

        try:
            for frame in frame_iterator:
                if self._stop_event.is_set():
                    break

                rms = self._rms(frame)
                is_speech = rms >= self.request.silence_threshold

                if not self._speech_started:
                    if is_speech:
                        self._speech_started = True
                        while self._preroll_frames:
                            buffered = self._preroll_frames.popleft()
                            chunk_frames.append(buffered)
                            self._captured_samples += len(buffered)
                        chunk_frames.append(frame)
                        self._captured_samples += len(frame)
                    else:
                        self._preroll_frames.append(frame)
                    continue

                chunk_frames.append(frame)
                self._captured_samples += len(frame)

                if is_speech:
                    silence_run_seconds = 0.0
                else:
                    silence_run_seconds += self._frame_duration_seconds

                if self._chunk_duration_seconds(chunk_frames) >= self.request.chunk_seconds:
                    self._flush_chunk(chunk_frames)
                    chunk_frames = []
                    silence_run_seconds = 0.0

                if silence_run_seconds >= self.request.silence_timeout_seconds:
                    end_reason = "silence_timeout"
                    break

                if (self._captured_samples / self.request.sample_rate) >= self.request.max_session_seconds:
                    end_reason = "max_duration_reached"
                    break

        except Exception as exc:
            final_status = "failed"
            end_reason = "error"
            with self._lock:
                self.error = str(exc)
            logger.exception("Audio session %s failed", self.session_id)

        # Final flush is intentionally outside the main try/except so that a
        # transient ASR error at the very end doesn't flip final_status to
        # "failed" and cause _finalize_run to skip RAG for an otherwise good
        # transcript.  Errors here are logged but treated as non-fatal.
        if chunk_frames and self._speech_started:
            try:
                self._flush_chunk(chunk_frames)
            except Exception as exc:
                logger.warning(
                    "Audio session %s: final flush failed (non-fatal): %s",
                    self.session_id, exc,
                )

        return final_status, end_reason

    def _finalize_run(self, final_status: str, end_reason: str) -> None:
        # Attempt RAG whenever there is a transcript, even if the session
        # ended with an error mid-stream (e.g. a transient ASR failure on one
        # chunk).  Only skip entirely when NO audio was captured at all.
        transcript = " ".join(part for part in self.transcript_parts if part).strip()
        if transcript:
            try:
                self._stream_rag_response(transcript)
            except Exception as exc:
                with self._lock:
                    self.error = str(exc)
                logger.exception("RAG query failed for session %s", self.session_id)
        elif final_status == "completed":
            self._synthesize_response("How can I help you?")

        with self._lock:
            if final_status == "completed" and self.end_reason == "stopped_by_api":
                end_reason = "stopped_by_api"
            self.status = final_status
            self.completed_at = datetime.now(UTC)
            self.end_reason = end_reason

        logger.info(
            "Session %s ended with reason=%s transcript=%s",
            self.session_id,
            self.end_reason,
            " ".join(self.transcript_parts).strip(),
        )
        if self.on_complete is not None:
            self.on_complete(self.session_id)

    def _synthesize_response(self, text: str) -> None:
        """Speak a fixed response directly via TTS, without calling RAG."""
        with self._lock:
            self.response_parts.append(text)
        sentence_queue: Queue[tuple[int | None, str | None]] = Queue()
        worker = threading.Thread(target=self._tts_worker, args=(sentence_queue,), daemon=True)
        worker.start()
        sentence_queue.put((1, text))
        sentence_queue.put((None, None))
        worker.join()

    def _stream_rag_response(self, transcript: str) -> None:
        pending_text = ""
        sentence_queue: Queue[tuple[int | None, str | None]] = Queue()
        worker = threading.Thread(target=self._tts_worker, args=(sentence_queue,), daemon=True)
        worker.start()

        print(f"\nRAG response for session {self.session_id}:\n", end="", flush=True)
        sentence_index = 0
        history = list(getattr(self.request, "history", []) or [])

        def _handle_rag_event(event: dict) -> None:
            if event.get("event") == "metrics":
                with self._lock:
                    perf = event.get("performance_metrics")
                    llm = event.get("llm_metrics")
                    if isinstance(perf, dict):
                        self.performance_metrics = dict(perf)
                    if isinstance(llm, dict):
                        self.llm_metrics = dict(llm)
                return

            if event.get("event") == "sources":
                sources = event.get("sources")
                if isinstance(sources, list):
                    with self._lock:
                        self.rag_sources = [s for s in sources if isinstance(s, dict)]

        try:
            for token in self.rag_client.stream_answer(
                transcript,
                history=history,
                include_sources=bool(getattr(self.request, "include_sources", False)),
                include_performance_metrics=bool(getattr(self.request, "include_performance_metrics", True)),
                include_llm_metrics=bool(getattr(self.request, "include_llm_metrics", True)),
                on_event=_handle_rag_event,
            ):
                with self._lock:
                    self.response_parts.append(token)
                print(token, end="", flush=True)

                pending_text += token
                complete_sentences, pending_text = self._drain_complete_sentences(pending_text)
                for sentence in complete_sentences:
                    sentence_index += 1
                    sentence_queue.put((sentence_index, sentence))

            trailing_text = pending_text.strip()
            if trailing_text:
                sentence_index += 1
                sentence_queue.put((sentence_index, trailing_text))
        finally:
            sentence_queue.put((None, None))
            worker.join()
            # Ubuntu implementation surfaces LLM metrics from rag-service
            # /api/v1/performance. Keep that behavior as a fallback when
            # SSE metrics events are not emitted by the query path.
            with self._lock:
                missing_metrics = (not self.performance_metrics) or (not self.llm_metrics)
            if missing_metrics:
                try:
                    perf_payload = self.rag_client.get_performance_metrics()
                    latency = perf_payload.get("latency") if isinstance(perf_payload, dict) else None
                    if isinstance(latency, dict):
                        with self._lock:
                            if not self.performance_metrics:
                                self.performance_metrics = {
                                    "retrieval": latency.get("retrieval") or {},
                                    "llm": latency.get("llm") or {},
                                }
                            if not self.llm_metrics:
                                llm = latency.get("llm")
                                self.llm_metrics = dict(llm) if isinstance(llm, dict) else {}
                except Exception:
                    # Keep streaming response resilient if performance endpoint
                    # is temporarily unavailable.
                    pass
            print(flush=True)

    @staticmethod
    def _drain_complete_sentences(buffer: str) -> tuple[list[str], str]:
        sentences: list[str] = []
        remaining = buffer
        while True:
            match = _SENTENCE_PATTERN.match(remaining.lstrip())
            if match is None:
                break
            sentence = match.group(1).strip()
            if sentence:
                sentences.append(sentence)
            remaining = remaining.lstrip()[match.end() :]
        return sentences, remaining

    def _tts_worker(self, sentence_queue: Queue[tuple[int | None, str | None]]) -> None:
        while True:
            sentence_index, sentence = sentence_queue.get()
            if sentence_index is None or sentence is None:
                return

            output_path = self._session_output_dir / f"response_{sentence_index:03d}.wav"
            try:
                self.tts_client.synthesize_to_file(
                    text=sentence,
                    output_path=str(output_path),
                    model=self.request.tts_model,
                    voice=self.request.tts_voice,
                    language=self.request.tts_language,
                    instructions=self.request.tts_instructions,
                )
                with self._lock:
                    self.tts_audio_segments.append(
                        {
                            "index": sentence_index,
                            "text": sentence,
                            "audio_file": str(output_path),
                        }
                    )
            except Exception as exc:
                logger.exception("TTS synthesis failed for session %s sentence %s", self.session_id, sentence_index)
                with self._lock:
                    self.tts_errors.append(f"sentence {sentence_index}: {exc}")

    def _on_audio(self, indata, frames, time, status) -> None:
        del frames, time
        if status:
            logger.warning("Audio callback status for %s: %s", self.session_id, status)
        self._audio_queue.put(indata[:, 0].copy())

    @staticmethod
    def _rms(frame: np.ndarray) -> float:
        samples = frame.astype(np.float32)
        return float(np.sqrt(np.mean(samples * samples)))

    def _chunk_duration_seconds(self, frames: list[np.ndarray]) -> float:
        total_samples = sum(len(frame) for frame in frames)
        return total_samples / self.request.sample_rate

    def _flush_chunk(self, frames: list[np.ndarray]) -> None:
        audio = np.concatenate(frames, axis=0)
        temp_path = self._write_temp_wav(audio)
        try:
            text = self.client.transcribe_file(
                temp_path,
                language=self.request.language,
                temperature=self.request.temperature,
            )
            if text:
                # Strip Whisper hallucination tokens (e.g. [BLANK_AUDIO], [Music])
                text = _WHISPER_JUNK.sub("", text).strip()
            if text:
                with self._lock:
                    self.transcript_parts.append(text)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _write_temp_wav(self, audio: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(prefix=f"{self.session_id}-", suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name

        with wave.open(temp_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.request.sample_rate)
            wav_file.writeframes(audio.astype(np.int16).tobytes())

        return temp_path


class BrowserStreamSession(BaseAudioSession):
    """Session that receives audio chunks pushed from the browser via HTTP.

    Call push_audio(wav_bytes) from the HTTP handler each time a chunk arrives.
    The session applies the same RMS silence detection and chunk-flushing logic
    as MicrophoneSession.  It ends automatically when:
      - silence_timeout_seconds of silence follows detected speech, OR
      - max_session_seconds of captured audio have been processed, OR
      - stop() is called explicitly (e.g. user clicks stop-recording in browser).
    """

    def __init__(
        self,
        request: SessionStartRequest,
        on_complete: Callable[[str], None] | None = None,
    ):
        super().__init__(request=request, on_complete=on_complete)
        self._thread = threading.Thread(target=self._run, name=f"browser-session-{self.session_id}", daemon=True)
        self._source_kind = "browser"
        # Sentinel: None means end-of-stream
        self._push_queue: Queue[np.ndarray | None] = Queue()

    def push_audio(self, wav_bytes: bytes) -> None:
        """Called from the HTTP handler for each incoming audio chunk."""
        audio = np.frombuffer(wav_bytes, dtype=np.int16)
        # Split into frame-sized pieces so _process_frame_stream sees uniform frames
        for start in range(0, len(audio), self._frame_samples):
            frame = audio[start : start + self._frame_samples]
            if len(frame) > 0:
                self._push_queue.put(frame.copy())

    def signal_end(self) -> None:
        """Signal that the browser has stopped recording (enqueue sentinel)."""
        self._push_queue.put(None)

    def _run(self) -> None:
        final_status = "completed"
        end_reason = self.end_reason or "completed"
        try:
            final_status, end_reason = self._process_frame_stream(self._iter_push_frames())
            if final_status == "completed" and not self._speech_started:
                end_reason = "no_speech_detected"
        except Exception as exc:
            final_status = "failed"
            end_reason = "error"
            with self._lock:
                self.error = str(exc)
            logger.exception("Browser stream session %s failed", self.session_id)
        finally:
            self._finalize_run(final_status, end_reason)

    def _iter_push_frames(self):
        while not self._stop_event.is_set():
            try:
                frame = self._push_queue.get(timeout=0.25)
            except Empty:
                continue
            if frame is None:
                # End-of-stream sentinel from signal_end()
                break
            yield frame


class MicrophoneSession(BaseAudioSession):
    def __init__(
        self,
        request: SessionStartRequest,
        on_complete: Callable[[str], None] | None = None,
    ):
        super().__init__(request=request, on_complete=on_complete)
        self._thread = threading.Thread(target=self._run, name=f"mic-session-{self.session_id}", daemon=True)
        self._source_kind = "microphone"

    def _run(self) -> None:
        final_status = "completed"
        end_reason = self.end_reason or "completed"
        try:
            with sd.InputStream(
                samplerate=self.request.sample_rate,
                blocksize=self._frame_samples,
                channels=1,
                dtype="int16",
                device=self.request.device,
                callback=self._on_audio,
            ):
                def iter_frames():
                    while not self._stop_event.is_set():
                        try:
                            yield self._audio_queue.get(timeout=0.25)
                        except Empty:
                            continue

                final_status, end_reason = self._process_frame_stream(iter_frames())
        except Exception as exc:
            final_status = "failed"
            end_reason = "error"
            with self._lock:
                self.error = str(exc)
            logger.exception("Microphone session %s failed", self.session_id)
        finally:
            self._finalize_run(final_status, end_reason)


class FileAudioSession(BaseAudioSession):
    def __init__(
        self,
        request: FileSessionStartRequest,
        audio_file_path: str,
        on_complete: Callable[[str], None] | None = None,
    ):
        super().__init__(request=request, on_complete=on_complete)
        self.request = request
        self.audio_file_path = audio_file_path
        self._thread = threading.Thread(target=self._run, name=f"file-session-{self.session_id}", daemon=True)
        self._source_kind = "file"

    def _run(self) -> None:
        final_status = "completed"
        end_reason = self.end_reason or "completed"
        try:
            final_status, end_reason = self._process_frame_stream(self._iter_file_frames())
            if final_status == "completed" and not self._speech_started:
                end_reason = "no_speech_detected"
        except Exception as exc:
            final_status = "failed"
            end_reason = "error"
            with self._lock:
                self.error = str(exc)
            logger.exception("File session %s failed", self.session_id)
        finally:
            Path(self.audio_file_path).unlink(missing_ok=True)
            self._finalize_run(final_status, end_reason)

    def _iter_file_frames(self):
        with wave.open(self.audio_file_path, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()

            if sample_width != 2:
                raise ValueError("Only 16-bit PCM WAV files are supported for file-based testing")
            if sample_rate != self.request.sample_rate:
                raise ValueError(
                    f"Uploaded WAV sample rate {sample_rate} does not match requested sample_rate {self.request.sample_rate}"
                )

            while not self._stop_event.is_set():
                raw = wav_file.readframes(self._frame_samples)
                if not raw:
                    break

                frame = np.frombuffer(raw, dtype=np.int16)
                if channels > 1:
                    frame = frame.reshape(-1, channels)[:, 0]

                if len(frame) == 0:
                    continue

                yield frame.copy()

                if self.request.realtime_factor > 0:
                    time.sleep((len(frame) / self.request.sample_rate) / self.request.realtime_factor)
