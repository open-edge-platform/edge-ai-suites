import os


# Service URLs - Windows native uses localhost, Docker uses service names
DEFAULT_ANALYZER_URL = os.getenv(
    "KIOSK_CORE_ANALYZER_URL",
    "http://127.0.0.1:8010/v1/audio/transcriptions",
)
DEFAULT_RAG_URL = os.getenv(
    "KIOSK_CORE_RAG_URL",
    "http://127.0.0.1:8020/api/v1/query",
)
DEFAULT_TTS_URL = os.getenv(
    "KIOSK_CORE_TTS_URL",
    "http://127.0.0.1:8011/v1/audio/speech",
)
DEFAULT_TTS_MODEL = os.getenv("KIOSK_CORE_TTS_MODEL", "qwen-tts")
DEFAULT_TTS_VOICE = os.getenv("KIOSK_CORE_TTS_VOICE")
DEFAULT_TTS_LANGUAGE = os.getenv("KIOSK_CORE_TTS_LANGUAGE", "English")
DEFAULT_TTS_INSTRUCTIONS = os.getenv("KIOSK_CORE_TTS_INSTRUCTIONS")
DEFAULT_SAMPLE_RATE = int(os.getenv("KIOSK_CORE_SAMPLE_RATE", "16000"))

# Metrics collector – Windows native uses localhost
# (For Docker deployments, would use http://metrics-collector:9000)
METRICS_COLLECTOR_URL = os.getenv(
    "KIOSK_CORE_METRICS_URL",
    "http://127.0.0.1:9000",
)
DEFAULT_CHUNK_SECONDS = float(os.getenv("KIOSK_CORE_CHUNK_SECONDS", "5.0"))
DEFAULT_SILENCE_TIMEOUT_SECONDS = float(os.getenv("KIOSK_CORE_SILENCE_TIMEOUT_SECONDS", "1.5"))
DEFAULT_MAX_SESSION_SECONDS = float(os.getenv("KIOSK_CORE_MAX_SESSION_SECONDS", "20.0"))
DEFAULT_SILENCE_THRESHOLD = int(os.getenv("KIOSK_CORE_SILENCE_THRESHOLD", "900"))
DEFAULT_BLOCK_DURATION_SECONDS = float(os.getenv("KIOSK_CORE_BLOCK_DURATION_SECONDS", "0.1"))
DEFAULT_PREROLL_SECONDS = float(os.getenv("KIOSK_CORE_PREROLL_SECONDS", "0.3"))
DEFAULT_HTTP_TIMEOUT_SECONDS = float(os.getenv("KIOSK_CORE_HTTP_TIMEOUT_SECONDS", "120.0"))
