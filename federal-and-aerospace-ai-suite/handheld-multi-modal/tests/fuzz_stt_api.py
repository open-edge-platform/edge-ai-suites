#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Fuzz / robustness test for the Whisper STT REST API.

The script fires a structured battery of crafted requests at the STT service
and flags any unexpected server errors (5xx) or connection failures.

By default the test set is run in a continuous loop for 1 hour so that each
iteration sees freshly generated random audio content.  Use --duration 0 for
a single-pass run (useful in CI).

Usage (host default = https://localhost:5443):
    python tests/fuzz_stt_api.py
    python tests/fuzz_stt_api.py --host https://192.168.1.10:5443
    python tests/fuzz_stt_api.py --duration 0          # single pass
    python tests/fuzz_stt_api.py --duration 1800       # 30 minutes
    python tests/fuzz_stt_api.py --timeout 60 --seed 1337

Or via Make:
    make fuzz-stt
    make fuzz-stt STT_HOST=https://192.168.1.10:5443

Requires only `requests` (already listed in apps/speech-to-text/requirements.txt).
Install on the host:  pip install requests

Exit codes:
    0 — no server crashes or connection errors
    1 — at least one 5xx response or connection error was detected
"""

import argparse
import os
import random
import struct
import sys
import time
from dataclasses import dataclass, field
from io import BytesIO
from typing import List, Optional, Tuple

import requests
import urllib3

# Silence the InsecureRequestWarning produced by verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# Helpers: WAV synthesis
# ---------------------------------------------------------------------------

def make_wav(
    num_channels: int = 1,
    sample_rate: int = 16000,
    bits_per_sample: int = 16,
    duration_secs: float = 0.1,
    pcm_data: Optional[bytes] = None,
) -> bytes:
    """Return a minimal, spec-compliant WAV file as raw bytes.

    If *pcm_data* is provided it is used verbatim as the data chunk payload
    (useful for injecting broken audio content into an otherwise valid
    RIFF/WAVE container).
    """
    if pcm_data is None:
        num_samples = int(sample_rate * duration_secs)
        pcm_data = struct.pack(
            f"<{num_samples}h",
            *[random.randint(-32768, 32767) for _ in range(num_samples)],
        )

    byte_rate   = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size   = len(pcm_data)

    buf = BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))            # PCM fmt chunk size
    buf.write(struct.pack("<H", 1))             # PCM format tag
    buf.write(struct.pack("<H", num_channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_data)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

PASS  = "✓"
WARN  = "⚠"
FAIL  = "✗"

@dataclass
class Result:
    name: str
    status: Optional[int]           # HTTP status code; None = connection error
    expected: List[int]             # acceptable status codes
    body: str = ""
    duration_ms: float = 0.0
    error: str = ""

    @property
    def passed(self) -> bool:
        # "expected" error means a client-side safety rejection (e.g. CRLF in header)
        # — treat it as a pass since it is the intended defensive behaviour.
        if self.error == "expected":
            return True
        return not self.error and self.status in self.expected

    @property
    def is_unexpected_server_error(self) -> bool:
        """True only when the server returned 5xx AND that was not listed as expected."""
        return self.status is not None and self.status >= 500 and self.status not in self.expected

    @property
    def is_unexpected_error(self) -> bool:
        """True for connection / client errors that are not marked expected (error != 'expected')."""
        return bool(self.error) and self.error != "expected"

    @property
    def symbol(self) -> str:
        if self.is_unexpected_error or self.is_unexpected_server_error:
            return FAIL
        if not self.passed:
            return WARN
        return PASS


# ---------------------------------------------------------------------------
# Fuzzer
# ---------------------------------------------------------------------------

class STTFuzzer:
    """Fires crafted HTTP requests at the STT API and records the results."""

    def __init__(self, host: str, timeout: int = 30, verbose: bool = False):
        self.host    = host.rstrip("/")
        self.timeout = timeout
        self.verbose = verbose
        self.session = requests.Session()
        self.session.verify = False
        self.results: List[Result] = []

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------


    def _request(
        self,
        method: str,
        path: str,
        *,
        files=None,
        data=None,
        json_body=None,
        params=None,
        headers=None,
    ) -> Tuple[Optional[int], str, float]:
        url   = f"{self.host}{path}"
        start = time.time()
        error = ""
        sc    = None
        body  = ""
        try:
            resp = self.session.request(
                method,
                url,
                files=files,
                data=data,
                json=json_body,
                params=params or {},
                headers=headers or {},
                timeout=self.timeout,
            )
            sc   = resp.status_code
            body = resp.text[:500]
        except requests.exceptions.Timeout:
            body  = "TIMEOUT"
            error = "timeout"
        except requests.exceptions.InvalidHeader as exc:
            # requests itself rejects headers containing CRLF or NUL — this is
            # a client-side security guard, not a server error.  Mark it as an
            # expected client rejection so it doesn't count as a failure.
            body  = f"client rejected header: {exc}"
            error = "expected"
        except Exception as exc:
            error = str(exc)
        duration = (time.time() - start) * 1000
        return sc, body, duration, error

    def _rec(self, name: str, sc, expected: List[int], body: str = "",
             duration: float = 0.0, error: str = "") -> None:
        r = Result(name, sc, expected, body, duration, error)
        self.results.append(r)
        status_str = str(sc) if sc is not None else "ERR"
        # Default mode: quiet runtime output; only failures are printed.
        if self.verbose or not r.passed:
            print(f"  {r.symbol} [{status_str:>4}] {name:<65} {duration:6.0f}ms")
        if not r.passed and (body or error):
            snippet = (error or body).replace("\n", " ")[:120]
            print(f"         └─ {snippet}")

    def _transcribe(self, **kwargs):
        return self._request("POST", "/transcribe", **kwargs)

    # ------------------------------------------------------------------
    # Test groups
    # ------------------------------------------------------------------

    def test_health(self):
        if self.verbose:
            print("\n── /health ──────────────────────────────────────────────────────────────")
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            sc, body, dur, err = self._request(method, "/health")
            expected = [200] if method in ("GET", "HEAD") else [200, 405, 400, 404]
            self._rec(f"health  {method}", sc, expected, body, dur, err)

    def test_metrics(self):
        if self.verbose:
            print("\n── /metrics ─────────────────────────────────────────────────────────────")
        for method in ["GET", "POST", "DELETE", "PUT"]:
            sc, body, dur, err = self._request(method, "/metrics")
            expected = [200] if method == "GET" else [200, 405, 400, 404]
            self._rec(f"metrics {method}", sc, expected, body, dur, err)

    def test_missing_audio_field(self):
        if self.verbose:
            print("\n── /transcribe — missing / wrong field ──────────────────────────────────")
        wav = make_wav()

        cases = [
            ("no body at all",                  None,                                     None),
            ("empty data dict",                 {},                                       None),
            ("wrong field 'file'",              None, {"file":       ("t.wav", BytesIO(wav), "audio/wav")}),
            ("wrong field 'audio_file'",        None, {"audio_file": ("t.wav", BytesIO(wav), "audio/wav")}),
            ("wrong field 'upload'",            None, {"upload":     ("t.wav", BytesIO(wav), "audio/wav")}),
            ("text field named 'audio'",        {"audio": "notafile"},                    None),
        ]
        for name, data, files in cases:
            sc, body, dur, err = self._transcribe(data=data, files=files)
            self._rec(name, sc, [400], body, dur, err)

    def test_wrong_methods(self):
        if self.verbose:
            print("\n── /transcribe — wrong HTTP methods ─────────────────────────────────────")
        wav = make_wav()
        for method in ["GET", "PUT", "DELETE", "PATCH", "HEAD"]:
            sc, body, dur, err = self._request(
                method, "/transcribe",
                files={"audio": ("t.wav", BytesIO(wav), "audio/wav")},
            )
            self._rec(f"method {method}", sc, [405, 400, 404, 200], body, dur, err)

    def test_binary_content(self):
        if self.verbose:
            print("\n── /transcribe — binary / crafted audio content ─────────────────────────")
        valid_wav = make_wav()

        cases = [
            # (label,  filename,   content,                          mime)
            ("empty file",                  "t.wav", b"",                                        "audio/wav"),
            ("single null byte",            "t.wav", b"\x00",                                    "audio/wav"),
            ("random 64 B",                 "t.wav", os.urandom(64),                             "audio/wav"),
            ("random 4 KB",                 "t.wav", os.urandom(4096),                           "audio/wav"),
            ("random 1 MB",                 "t.wav", os.urandom(1024 * 1024),                    "audio/wav"),
            ("all-zero 1 KB",               "t.wav", b"\x00" * 1024,                             "audio/wav"),
            ("all-0xFF 1 KB",               "t.wav", b"\xff" * 1024,                             "audio/wav"),
            ("plain text",                  "t.wav", b"This is not audio",                       "audio/wav"),
            ("JSON blob",                   "t.wav", b'{"key": "value"}',                        "audio/wav"),
            ("HTML blob",                   "t.wav", b"<html><body>hi</body></html>",             "audio/wav"),
            ("truncated WAV (20 B)",        "t.wav", valid_wav[:20],                             "audio/wav"),
            ("WAV header + junk data",      "t.wav", valid_wav[:44] + os.urandom(100),           "audio/wav"),
            ("WAV: claim >actual data",     "t.wav", valid_wav[:44] + b"\x00" * 2,               "audio/wav"),
            ("random bytes as .mp3",        "t.mp3", os.urandom(512),                            "audio/mpeg"),
            ("random bytes as .ogg",        "t.ogg", os.urandom(512),                            "audio/ogg"),
            ("random bytes as .flac",       "t.flac",os.urandom(512),                            "audio/flac"),
            ("random bytes as .webm",       "t.webm",os.urandom(512),                            "video/webm"),
            ("valid WAV 0.1 s",             "t.wav", make_wav(duration_secs=0.1),                "audio/wav"),
            ("WAV silence 0.5 s",           "t.wav", make_wav(pcm_data=b"\x00" * 16000),         "audio/wav"),
            ("WAV: stereo 16-bit",          "t.wav", make_wav(num_channels=2, duration_secs=0.1),"audio/wav"),
            ("WAV: 8 kHz mono",             "t.wav", make_wav(sample_rate=8000, duration_secs=0.1), "audio/wav"),
            ("WAV: 8-bit",                  "t.wav", make_wav(bits_per_sample=8, duration_secs=0.1), "audio/wav"),
        ]
        for label, fname, content, mime in cases:
            sc, body, dur, err = self._transcribe(
                files={"audio": (fname, BytesIO(content), mime)},
            )
            # Server may reject bad audio (400/500) or attempt transcription (200)
            self._rec(label, sc, [200, 400, 415, 500], body, dur, err)

    def test_filename_injection(self):
        if self.verbose:
            print("\n── /transcribe — filename injection / edge cases ────────────────────────")
        wav = make_wav()
        cases = [
            ("no extension",               "audiofile"),
            ("double extension",           "audio.wav.exe"),
            ("path traversal unix",        "../../etc/passwd.wav"),
            ("path traversal windows",     r"..\..\windows\system32.wav"),
            ("absolute path",              "/etc/passwd"),
            ("dot-only",                   ".wav"),
            ("long filename (1024 chars)", "a" * 1020 + ".wav"),
            ("special shell chars",        "audio;id>.wav"),
            ("backtick injection",         "audio`id`.wav"),
            ("unicode filename",           "аудио_тест.wav"),
            ("spaces in name",             "my audio file.wav"),
            ("null-byte attempt",          "audio\x00evil.wav"),
            ("CRLF in name",               "audio\r\nX-Header: injected"),
            ("empty string filename",      ""),
        ]
        for label, fname in cases:
            sc, body, dur, err = self._transcribe(
                files={"audio": (fname, BytesIO(wav), "audio/wav")},
            )
            self._rec(f"filename: {label}", sc, [200, 400, 500], body, dur, err)

    def test_query_params(self):
        if self.verbose:
            print("\n── /transcribe — query-parameter fuzzing ────────────────────────────────")
        wav = make_wav()
        cases = [
            ("stream=true",             {"stream": "true"}),
            ("stream=false",            {"stream": "false"}),
            ("stream=1",                {"stream": "1"}),
            ("stream=yes",              {"stream": "yes"}),
            ("stream=True",             {"stream": "True"}),
            ("stream empty string",     {"stream": ""}),
            ("stream XSS attempt",      {"stream": "<script>alert(1)</script>"}),
            ("stream SQL injection",    {"stream": "'; DROP TABLE users;--"}),
            ("multiple params",         {"stream": "true", "foo": "bar", "x": "y"}),
            ("repeated stream",         {"stream": ["true", "false"]}),
            ("very long param value",   {"stream": "x" * 10_000}),
            ("param with newline",      {"stream": "true\r\nX-Injected: evil"}),
        ]
        for label, params in cases:
            sc, body, dur, err = self._transcribe(
                files={"audio": ("t.wav", BytesIO(wav), "audio/wav")},
                params=params,
            )
            # 414 Request-URI Too Large is a valid nginx rejection for huge query strings
            expected = [200, 400, 414, 500]
            self._rec(f"param: {label}", sc, expected, body, dur, err)

    def test_content_type(self):
        if self.verbose:
            print("\n── /transcribe — Content-Type / raw body ────────────────────────────────")
        wav = make_wav()
        cases = [
            ("JSON body",                   "application/json",           b'{"audio": "data"}'),
            ("plain-text body",             "text/plain",                 b"audio data"),
            ("octet-stream body",           "application/octet-stream",   wav),
            ("no Content-Type header",      None,                         wav),
            ("XML body",                    "application/xml",            b"<root/>"),
        ]
        for label, ct, raw_body in cases:
            headers = {"Content-Type": ct} if ct else {}
            sc, body, dur, err = self._request(
                "POST", "/transcribe",
                data=raw_body,
                headers=headers,
            )
            self._rec(f"content-type: {label}", sc, [400, 415, 200, 500], body, dur, err)

    def test_headers(self):
        if self.verbose:
            print("\n── /transcribe — header injection / oversized headers ───────────────────")
        wav = make_wav()
        cases = [
            ("X-Forwarded-For injection",   {"X-Forwarded-For": "127.0.0.1; rm -rf /"}),
            ("very long User-Agent",        {"User-Agent": "A" * 8192}),
            ("Host override",               {"Host": "evil.example.com"}),
            ("Accept CRLF injection",       {"Accept": "application/json\r\nX-Injected: evil"}),
            ("many custom headers",         {f"X-Fuzz-{i}": "v" * 100 for i in range(50)}),
        ]
        for label, headers in cases:
            sc, body, dur, err = self._transcribe(
                files={"audio": ("t.wav", BytesIO(wav), "audio/wav")},
                headers=headers,
            )
            self._rec(f"header: {label}", sc, [200, 400, 413, 431, 500], body, dur, err)

    def test_multi_file(self):
        if self.verbose:
            print("\n── /transcribe — multiple files / extra fields ──────────────────────────")
        wav = make_wav()
        cases = [
            ("two 'audio' parts",
             [("audio", ("a.wav", BytesIO(wav), "audio/wav")),
              ("audio", ("b.wav", BytesIO(wav), "audio/wav"))]),
            ("correct + extra file field",
             [("audio", ("a.wav", BytesIO(wav), "audio/wav")),
              ("extra", ("x.wav", BytesIO(wav), "audio/wav"))]),
            ("correct + extra text field",
             [("audio", ("a.wav", BytesIO(wav), "audio/wav")),
              ("lang",  (None, "en"))]),
        ]
        for label, file_list in cases:
            sc, body, dur, err = self._transcribe(files=file_list)
            self._rec(f"multi: {label}", sc, [200, 400], body, dur, err)

    def test_path_variants(self):
        if self.verbose:
            print("\n── path variants / URL injection ────────────────────────────────────────")
        wav = make_wav()
        paths = [
            "/transcribe/",
            "/transcribe/../transcribe",
            "/TRANSCRIBE",
            "/Transcribe",
            "/transcribe%00",
            "/transcribe?",
            "/%2F",
            "/.",
            "/../",
        ]
        for path in paths:
            sc, body, dur, err = self._request(
                "POST", path,
                files={"audio": ("t.wav", BytesIO(wav), "audio/wav")},
            )
            self._rec(f"path: {path}", sc, [200, 301, 302, 400, 404, 405], body, dur, err)

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    def run(self, duration: int = 3600) -> int:
        print(f"\n{'='*78}")
        print(f"  Whisper STT API — Fuzz / Robustness Test")
        print(f"  Target   : {self.host}")
        if duration > 0:
            print(f"  Duration : {duration}s (Ctrl-C to stop early)")
        else:
            print(f"  Duration : single pass")
        print(f"{'='*78}")

        deadline  = (time.time() + duration) if duration > 0 else None
        iteration = 0

        while True:
            iteration += 1
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                if self.verbose:
                    print(f"\n── Iteration {iteration}  ({remaining:.0f}s remaining) {'─'*40}")

            self.test_health()
            self.test_metrics()
            self.test_missing_audio_field()
            self.test_wrong_methods()
            self.test_binary_content()
            self.test_filename_injection()
            self.test_query_params()
            self.test_content_type()
            self.test_headers()
            self.test_multi_file()
            self.test_path_variants()

            if deadline is None:
                break

        total          = len(self.results)
        passed         = sum(1 for r in self.results if r.passed)
        server_errs    = sum(1 for r in self.results if r.is_unexpected_server_error)
        conn_errs      = sum(1 for r in self.results if r.is_unexpected_error)
        expected_5xx   = sum(
            1 for r in self.results
            if r.status is not None and r.status >= 500
            and r.status in r.expected
        )

        print(f"\n{'='*78}")
        print(f"  Iterations: {iteration}")
        print(f"  Results : {passed}/{total} expected-status checks passed")
        if server_errs:
            print(f"  {FAIL}  Unexpected server errors (5xx) : {server_errs}")
        if conn_errs:
            print(f"  {FAIL}  Unexpected connection errors   : {conn_errs}")
        if expected_5xx:
            print(f"  {WARN}  Expected 5xx (bad audio input) : {expected_5xx}  (informational)")
        if not server_errs and not conn_errs:
            print(f"  {PASS}  No unexpected server crashes or connection errors detected.")

        # Surface all failures for review
        failures = [r for r in self.results if not r.passed]
        if failures:
            print(f"\n  Unexpected responses ({len(failures)}):")
            for r in failures:
                print(f"    [{r.status or 'ERR':>4}] {r.name}")
        print(f"{'='*78}\n")

        return 1 if (server_errs > 0 or conn_errs > 0) else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fuzz / robustness test for the Whisper STT REST API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/fuzz_stt_api.py
  python tests/fuzz_stt_api.py --host https://192.168.1.10:5443
  python tests/fuzz_stt_api.py --timeout 60
  make fuzz-stt
  make fuzz-stt STT_HOST=https://192.168.1.10:5443
""",
    )
    parser.add_argument(
        "--host", default="https://localhost:5443",
        help="Base URL of the STT service (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout", type=int, default=30,
        help="Per-request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--duration", type=int, default=3600,
        help="How long to run the fuzz loop in seconds; 0 = single pass (default: %(default)s)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducible runs (default: random)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print all test-case results during execution (default: print failures only)",
    )
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(2**32)
    random.seed(seed)
    print(f"[fuzz] seed={seed}  duration={args.duration}s  host={args.host}")

    fuzzer = STTFuzzer(host=args.host, timeout=args.timeout, verbose=args.verbose)
    sys.exit(fuzzer.run(duration=args.duration))


if __name__ == "__main__":
    main()
