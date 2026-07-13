import threading
import tempfile
from pathlib import Path

import sounddevice as sd
from fastapi import UploadFile

from kiosk_core.audio_session import BrowserStreamSession, FileAudioSession, MicrophoneSession
from kiosk_core.models import FileSessionStartRequest, SessionStartRequest, SessionStopResponse


class SessionService:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, MicrophoneSession | FileAudioSession | BrowserStreamSession] = {}
        self._active_session_id: str | None = None

    def start_session(self, request: SessionStartRequest) -> dict[str, object]:
        with self._lock:
            if self._active_session_id is not None:
                active = self._sessions[self._active_session_id]
                if active.snapshot()["status"] in {"running", "stopping"}:
                    raise ValueError("Another microphone session is already active")

            session = MicrophoneSession(request=request, on_complete=self._on_session_complete)
            self._sessions[session.session_id] = session
            self._active_session_id = session.session_id
            session.start()
            return session.snapshot()

    def start_file_session(self, request: FileSessionStartRequest, upload: UploadFile) -> dict[str, object]:
        suffix = Path(upload.filename or "audio.wav").suffix or ".wav"
        with self._lock:
            if self._active_session_id is not None:
                active = self._sessions[self._active_session_id]
                if active.snapshot()["status"] in {"running", "stopping"}:
                    raise ValueError("Another audio session is already active")

            with tempfile.NamedTemporaryFile(prefix="kiosk-upload-", suffix=suffix, delete=False) as temp_file:
                temp_file.write(upload.file.read())
                temp_path = temp_file.name

            session = FileAudioSession(request=request, audio_file_path=temp_path, on_complete=self._on_session_complete)
            self._sessions[session.session_id] = session
            self._active_session_id = session.session_id
            session.start()
            return session.snapshot()

    def stop_session(self, session_id: str) -> SessionStopResponse:
        session = self._get_session_obj(session_id)
        session.stop()
        snapshot = session.snapshot()
        return SessionStopResponse(
            session_id=session_id,
            status=str(snapshot["status"]),
            stop_requested_at=session.stop_requested_at,
        )

    def get_session(self, session_id: str) -> dict[str, object]:
        return self._get_session_obj(session_id).snapshot()

    def list_sessions(self) -> list[dict[str, object]]:
        with self._lock:
            return [session.snapshot() for session in self._sessions.values()]

    def list_input_devices(self) -> list[dict[str, str | int]]:
        devices = []
        for index, device in enumerate(sd.query_devices()):
            if int(device["max_input_channels"]) <= 0:
                continue
            devices.append(
                {
                    "id": index,
                    "name": str(device["name"]),
                    "default_samplerate": int(device["default_samplerate"]),
                }
            )
        return devices

    def start_stream_session(self, request: SessionStartRequest) -> dict[str, object]:
        with self._lock:
            if self._active_session_id is not None:
                active = self._sessions[self._active_session_id]
                if active.snapshot()["status"] in {"running", "stopping"}:
                    raise ValueError("Another audio session is already active")

            session = BrowserStreamSession(request=request, on_complete=self._on_session_complete)
            self._sessions[session.session_id] = session
            self._active_session_id = session.session_id
            session.start()
            return session.snapshot()

    def push_audio_chunk(self, session_id: str, wav_bytes: bytes) -> None:
        session = self._get_session_obj(session_id)
        if not isinstance(session, BrowserStreamSession):
            raise ValueError("Session is not a browser stream session")
        if session.snapshot()["status"] not in {"running", "stopping"}:
            raise ValueError("Session is not active")
        session.push_audio(wav_bytes)

    def signal_stream_end(self, session_id: str) -> None:
        session = self._get_session_obj(session_id)
        if not isinstance(session, BrowserStreamSession):
            raise ValueError("Session is not a browser stream session")
        session.signal_end()

    def _get_session_obj(self, session_id: str) -> MicrophoneSession | FileAudioSession | BrowserStreamSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        return session

    def _on_session_complete(self, session_id: str) -> None:
        with self._lock:
            if self._active_session_id == session_id:
                self._active_session_id = None