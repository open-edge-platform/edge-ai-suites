# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# -*- encoding: utf-8 -*-
"""Standalone TTS WebSocket server for utils/tts_client.py.

Protocol (JSON over WebSocket):
- action=submit_tts  -> enqueue one text, server handles generate + play asynchronously
- action=health      -> report model/server readiness
- action=test        -> run one end-to-end test (generate + play) synchronously

Run:
    python tts_server.py --host 0.0.0.0 --port 10096
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import websockets


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TTSInferenceEngine:
    """Embedded OpenVoice/MeloTTS runtime used by this server only."""

    home_dir = os.path.expanduser("~")
    openvoice_src_path = os.getenv("OPENVOICE_SRC_PATH", f"{home_dir}/ov_models/TTS/OpenVoice")
    melotts_src_path = os.getenv("MELOTTS_SRC_PATH", f"{home_dir}/ov_models/TTS/MeloTTS")
    torch_hub_local_path = os.getenv("TORCH_HUB_LOCAL_PATH", f"{home_dir}/ov_models/TTS/torch_hub_local")
    ckpt_base_path = os.getenv("OPENVOICE_CKPT_BASE_PATH", f"{home_dir}/ov_models/TTS/checkpoints")
    irs_path = os.getenv("OPENVOICE_IRS_PATH", f"{home_dir}/ov_models/TTS/openvino_irs")
    reference_speaker_path = os.getenv(
        "OPENVOICE_REFERENCE_SPEAKER_PATH",
        f"{home_dir}/ov_models/TTS/OpenVoice/resources/demo_speaker1.mp3",
    )

    def __init__(self):
        os.environ["TORCH_HOME"] = self.torch_hub_local_path

        self._initialized = False
        self._enable_openvoice = True
        self._se_extractor = None

        self.last_tts_result: Optional[str] = None
        self.cached_audio_path: Optional[str] = None

        self.device = "GPU"
        self.reference_speaker = self.reference_speaker_path
        self.output_dir = str(Path(__file__).resolve().parent / "outputs")
        self.runtime_output_path = str(Path(self.output_dir) / "runtime_tts.wav")

        self.core = None
        self.tts_model = None
        self.tone_color_converter = None
        self.source_se = None
        self.target_se = None
        self.speaker_id = 0
        self.temp_audio_path = Path(self.output_dir) / "temp_en.wav"

        self._initialize_models()

        if self.model_ready and self.target_se is None:
            try:
                self.target_se, _ = self._se_extractor.get_se(
                    self.reference_speaker,
                    self.tone_color_converter,
                    target_dir=self.output_dir,
                    vad=True,
                )
            except Exception as exc:
                self._enable_openvoice = False
                logger.warning("[TTS][INIT] failed to extract target speaker embedding: %s", exc)

    @property
    def model_ready(self) -> bool:
        return bool(self._enable_openvoice and self._initialized)

    def get_patched_infer(self, ov_model, device, core):
        import torch

        compiled_model = core.compile_model(ov_model, device)

        def infer_impl(
            x,
            x_lengths,
            sid,
            tone,
            language,
            bert,
            ja_bert,
            noise_scale,
            length_scale,
            noise_scale_w,
            max_len=None,
            sdp_ratio=1.0,
            y=None,
            g=None,
        ):
            ov_output = compiled_model(
                (
                    x,
                    x_lengths,
                    sid,
                    tone,
                    language,
                    bert,
                    ja_bert,
                    noise_scale,
                    length_scale,
                    noise_scale_w,
                    sdp_ratio,
                )
            )
            return (torch.tensor(ov_output[0]),)

        return infer_impl

    def get_patched_voice_conversion(self, ov_model, device, core):
        import torch

        compiled_model = core.compile_model(ov_model, device)

        def voice_conversion_impl(y, y_lengths, sid_src, sid_tgt, tau):
            ov_output = compiled_model((y, y_lengths, sid_src, sid_tgt, tau))
            return (torch.tensor(ov_output[0]),)

        return voice_conversion_impl

    def _initialize_models(self):
        if self._initialized:
            return

        try:
            if self.openvoice_src_path not in sys.path:
                sys.path.append(self.openvoice_src_path)
            if self.melotts_src_path not in sys.path:
                sys.path.append(self.melotts_src_path)

            import torch
            import openvino as ov
            from openvoice.api import ToneColorConverter
            import openvoice.se_extractor as se_extractor
            from melo.api import TTS

            torch.set_num_threads(3)
            torch.set_num_interop_threads(3)
            self._se_extractor = se_extractor

            ckpt_base_path = Path(self.ckpt_base_path)
            base_speakers_suffix = ckpt_base_path / "base_speakers" / "ses"
            converter_suffix = ckpt_base_path / "converter"
            melotts_english_suffix = ckpt_base_path / "MeloTTS-English-v3"
            irs_path = Path(self.irs_path)

            en_tts_ir = irs_path / "melo_tts_en_newest.xml"
            voice_converter_ir = irs_path / "openvoice2_tone_conversion.xml"

            required_paths = [
                en_tts_ir,
                voice_converter_ir,
                melotts_english_suffix / "config.json",
                melotts_english_suffix / "checkpoint.pth",
                converter_suffix / "config.json",
                converter_suffix / "checkpoint.pth",
                base_speakers_suffix / "en-newest.pth",
                Path(self.reference_speaker),
            ]
            missing_paths = [str(p) for p in required_paths if not Path(p).exists()]
            if missing_paths:
                raise FileNotFoundError(f"missing required files: {missing_paths}")

            self.core = ov.Core()
            ov_en_tts = self.core.read_model(en_tts_ir)
            ov_voice_conversion = self.core.read_model(voice_converter_ir)
            pt_device = "cpu"

            melo_tts_en = TTS(
                "EN_NEWEST",
                pt_device,
                use_hf=False,
                config_path=melotts_english_suffix / "config.json",
                ckpt_path=melotts_english_suffix / "checkpoint.pth",
            )

            self.tone_color_converter = ToneColorConverter(str(converter_suffix / "config.json"), device=pt_device)
            self.tone_color_converter.load_ckpt(str(converter_suffix / "checkpoint.pth"))

            speaker_ckpt = base_speakers_suffix / "en-newest.pth"
            try:
                self.source_se = torch.load(speaker_ckpt, map_location=pt_device, weights_only=True)
            except TypeError:
                self.source_se = torch.load(speaker_ckpt, map_location=pt_device)

            melo_tts_en.model.infer = self.get_patched_infer(ov_en_tts, self.device, self.core)
            self.tts_model = melo_tts_en
            self.tone_color_converter.model.voice_conversion = self.get_patched_voice_conversion(
                ov_voice_conversion,
                self.device,
                self.core,
            )

            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            self._initialized = True
            logger.info("[TTS] embedded engine initialized")
        except Exception as exc:
            self._enable_openvoice = False
            self._initialized = False
            logger.exception("[TTS] embedded engine init failed: %s", exc)

    def get_tts_result(self, text: str) -> Optional[str]:
        if not self.model_ready:
            return None
        try:
            self.tts_model.tts_to_file(text, self.speaker_id, str(self.temp_audio_path), speed=1.0)
            self.tone_color_converter.convert(
                audio_src_path=str(self.temp_audio_path),
                src_se=self.source_se,
                tgt_se=self.target_se,
                output_path=self.runtime_output_path,
                tau=0.3,
                message="@MyShell",
            )
            self.last_tts_result = self.runtime_output_path
            self.cached_audio_path = self.runtime_output_path
            return self.last_tts_result
        except Exception as exc:
            logger.exception("[TTS] inference failed: %s", exc)
            return None

    def speak_tts_result(self) -> bool:
        if not self.model_ready:
            return False

        play_path = self.cached_audio_path or self.runtime_output_path
        if not play_path or not Path(play_path).exists():
            logger.warning("[TTS] audio file does not exist: %s", play_path)
            return False
        try:
            subprocess.run(
                [
                    "ffplay",
                    "-nodisp",
                    "-autoexit",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    str(play_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return True
        except OSError as exc:
            logger.warning("[TTS] failed to invoke ffplay: %s", exc)
            return False


class TTSService:
    def __init__(self, max_queue_size: int = 16):
        self.engine = TTSInferenceEngine()
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=max_queue_size)
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="TTSServiceWorker")
        self._worker_thread.start()

        self.last_error = ""
        self.last_job_id = ""
        self.last_job_text = ""
        self.last_finish_ts = 0.0

    @property
    def model_ready(self) -> bool:
        return self.engine.model_ready

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def stop(self):
        self._running = False
        try:
            self._queue.put_nowait(("", ""))
        except queue.Full:
            pass
        self._worker_thread.join(timeout=3.0)

    def submit(self, request_id: str, text: str) -> Dict[str, Any]:
        if not text or not text.strip():
            return self._error(request_id, "empty input text")

        if not self.model_ready:
            return self._error(request_id, "tts model not ready")

        try:
            self._queue.put_nowait((request_id, text))
        except queue.Full:
            return {
                "request_id": request_id,
                "accepted": False,
                "status": "busy",
                "message": "tts queue is full",
            }

        return {
            "request_id": request_id,
            "accepted": True,
            "status": "accepted",
            "message": "tts request queued",
            "queue_size": self.queue_size,
        }

    def health(self, request_id: str) -> Dict[str, Any]:
        if self.model_ready:
            return {
                "request_id": request_id,
                "accepted": True,
                "status": "ready",
                "message": "tts service is ready",
                "queue_size": self.queue_size,
                "last_error": self.last_error,
            }
        return self._error(request_id, "tts model not ready")

    def self_test(self, request_id: str, text: str) -> Dict[str, Any]:
        if not self.model_ready:
            return self._error(request_id, "tts model not ready")

        try:
            t0 = time.perf_counter()
            result = self.engine.get_tts_result(text)
            played = self.engine.speak_tts_result()
            t1 = time.perf_counter()
            return {
                "request_id": request_id,
                "accepted": bool(result),
                "status": "completed" if result else "error",
                "message": "tts self test completed" if result else "tts self test failed",
                "result": result,
                "played": played,
                "latency_s": round(t1 - t0, 4),
            }
        except Exception as exc:
            logger.exception("[TTS server] self_test failed: %s", exc)
            self.last_error = str(exc)
            return self._error(request_id, str(exc))

    def _error(self, request_id: str, message: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "accepted": False,
            "status": "error",
            "error": message,
        }

    def _worker_loop(self):
        while self._running:
            try:
                request_id, text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if not self._running:
                break
            if not text:
                continue

            try:
                logger.info("[TTS server] processing job request_id=%s", request_id)
                t0 = time.perf_counter()
                result = self.engine.get_tts_result(text)
                t1 = time.perf_counter()
                played = self.engine.speak_tts_result()
                t2 = time.perf_counter()
                self.last_job_id = request_id
                self.last_job_text = text
                self.last_finish_ts = time.time()
                self.last_error = ""
                logger.info("tts inference time: %.4fs, tts play time: %.4fs", t1 - t0, t2 - t1)
                logger.info("[TTS server] completed job request_id=%s result=%s played=%s", request_id, result, played)
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("[TTS server] job failed request_id=%s: %s", request_id, exc)
            finally:
                self._queue.task_done()


async def handle_client(websocket, service: TTSService):
    try:
        raw = await websocket.recv()
        req = json.loads(raw)
    except Exception as exc:
        await websocket.send(json.dumps({"accepted": False, "status": "error", "error": f"bad request: {exc}"}))
        return

    action = req.get("action", "")
    request_id = str(req.get("request_id", "")) or "unknown"

    if action == "submit_tts":
        response = service.submit(request_id=request_id, text=str(req.get("text", "")))
        await websocket.send(json.dumps(response, ensure_ascii=False))
        return

    if action == "health":
        response = service.health(request_id=request_id)
        await websocket.send(json.dumps(response, ensure_ascii=False))
        return

    if action == "test":
        text = str(req.get("text", "This is a TTS service self test."))
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, service.self_test, request_id, text)
        await websocket.send(json.dumps(response, ensure_ascii=False))
        return

    await websocket.send(
        json.dumps(
            {
                "request_id": request_id,
                "accepted": False,
                "status": "error",
                "error": f"unsupported action: {action}",
            },
            ensure_ascii=False,
        )
    )


async def start_server(host: str, port: int):
    service = TTSService()

    async def _handler(websocket):
        await handle_client(websocket, service)

    stop_event = asyncio.Event()

    def _request_stop(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Platform-specific limitation (e.g. some embedded runtimes)
            pass

    logger.info("[TTS server] starting on ws://%s:%s", host, port)
    async with websockets.serve(_handler, host, port, ping_interval=None):
        await stop_event.wait()

    service.stop()
    logger.info("[TTS server] stopped")


def main():
    parser = argparse.ArgumentParser(description="Standalone TTS WebSocket server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="bind host")
    parser.add_argument("--port", type=int, default=10096, help="bind port")
    args = parser.parse_args()

    asyncio.run(start_server(args.host, args.port))


if __name__ == "__main__":
    main()
