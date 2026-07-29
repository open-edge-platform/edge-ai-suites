"""
telegram_sender.py
------------------
Sends session data packages to a Telegram group so that OpenClaw (Linux)
can answer the following queries from the shared chat:

  Q1 – "What topics did we cover in today's class?"
  Q2 – "How engaged were the students today?"
  Q3 – "My child was absent — what did they miss?"
  Q4 – "Which students participated the most today?"

Package A  (sent after content-segmentation completes)  →  answers Q1, Q3
  Files: session_meta.json, summary.md, topics.json, mindmap.mmd

Package B+C  (sent when VA pipeline stops)  →  answers Q2, Q4
  Files: engagement_report.json, participation_report.json

Activation: set  telegram.enabled: true  in config.yaml
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime

import socks
from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


# ── Singleton ─────────────────────────────────────────────────────────────────

_sender_instance = None


def get_sender():
    """Return the configured TelegramSender singleton, or None if disabled."""
    global _sender_instance
    if _sender_instance is not None:
        return _sender_instance
    try:
        from utils.config_loader import config  # lazy import avoids circular refs
        tg = getattr(config, "telegram", None)
        if tg and getattr(tg, "enabled", False):
            proxy_cfg = getattr(tg, "proxy", None)
            proxy = None
            if proxy_cfg and getattr(proxy_cfg, "host", ""):
                ptype = socks.SOCKS5 if str(getattr(proxy_cfg, "type", "http")).lower() == "socks5" else socks.HTTP
                user = getattr(proxy_cfg, "username", "") or None
                pwd  = getattr(proxy_cfg, "password", "") or None
                proxy = (ptype, str(proxy_cfg.host), int(proxy_cfg.port), True, user, pwd)
            _sender_instance = TelegramSender(
                api_id=int(tg.api_id),
                api_hash=str(tg.api_hash),
                session_string=str(tg.session_string),
                chat_id=int(str(tg.chat_id)),
                class_name=getattr(tg, "class_name", "Smart Classroom"),
                proxy=proxy,
            )
            logger.info("[Telegram] Sender initialised (userbot).")
    except Exception as exc:
        logger.error(f"[Telegram] Failed to initialise sender: {exc}")
    return _sender_instance


# ── Core class ────────────────────────────────────────────────────────────────

class TelegramSender:
    def __init__(self, api_id: int, api_hash: str, session_string: str,
                 chat_id: int, class_name: str, proxy=None):
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_string = session_string
        self._chat_id = chat_id
        self._class_name = class_name
        self._proxy = proxy

    def _make_client(self) -> TelegramClient:
        return TelegramClient(
            StringSession(self._session_string),
            self._api_id,
            self._api_hash,
            proxy=self._proxy,
        )

    # ── Low-level async helpers (take an already-connected client) ────────────

    async def _send_message_async(self, client: TelegramClient, text: str):
        try:
            await client.send_message(self._chat_id, text, parse_mode="md")
        except Exception as exc:
            logger.error(f"[Telegram] send_message failed: {exc}")

    async def _send_file_async(self, client: TelegramClient,
                               file_path: str, caption: str = ""):
        try:
            await client.send_file(self._chat_id, file_path, caption=caption)
        except Exception as exc:
            logger.error(f"[Telegram] send_file failed for {file_path}: {exc}")

    # ── Package A — Session Content ───────────────────────────────────────────

    async def _content_package_coro(self, session_id: str, session_dir: str):
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M")

        meta = {
            "schema": "smart_classroom_session_v1",
            "package": "content",
            "session_id": session_id,
            "class_name": self._class_name,
            "date": date_str,
            "time": time_str,
            "files": {
                "summary": "summary.md",
                "topics":  "topics.json",
                "mindmap": "mindmap.mmd",
            },
            "openclaw_hints": {
                "Q1_topics_covered":   "Read topics.json for the timestamped list; read ## Session Outline in summary.md for human-readable form.",
                "Q3_absentee_catchup": "summary.md contains the full lesson content. topics.json gives a timed breakdown the student can use for self-study.",
            },
        }

        meta_path = os.path.join(session_dir, "session_meta.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        async with self._make_client() as client:
            await self._send_message_async(
                client,
                f"**Session Content Ready**\n"
                f"Class: {self._class_name}\n"
                f"Session: `{session_id}`\n"
                f"Date: {date_str}  |  Time: {time_str}\n\n"
                f"_Provides data for Q1 (topics covered) and Q3 (absentee catch-up)_",
            )
            for fname, caption in [
                ("session_meta.json", "Envelope — load this first (Q1 / Q3)"),
                ("summary.md",        "Q1 / Q3 — Lesson summary with key takeaways and session outline"),
                ("topics.json",       "Q1 / Q3 — Timestamped topic segments"),
                ("mindmap.mmd",       "Q1     — Mind map of lesson concepts (Mermaid format)"),
            ]:
                path = os.path.join(session_dir, fname)
                if os.path.exists(path):
                    await self._send_file_async(client, path, caption)
                else:
                    logger.warning(f"[Telegram] Package A: {fname} not found, skipping")

        logger.info(f"[Telegram] Package A sent for session {session_id}")

    def send_content_package(self, session_id: str, session_dir: str):
        asyncio.run(self._content_package_coro(session_id, session_dir))

    # ── Package B+C — Engagement & Participation ──────────────────────────────

    async def _engagement_package_coro(self, session_id: str, session_dir: str,
                                       va_posture_file: str = None):
        date_str = datetime.now().strftime("%Y-%m-%d")
        engagement, participation = self._build_engagement_data(
            session_id, date_str, session_dir, va_posture_file
        )

        eng_path  = os.path.join(session_dir, "engagement_report.json")
        part_path = os.path.join(session_dir, "participation_report.json")

        with open(eng_path, "w", encoding="utf-8") as fh:
            json.dump(engagement, fh, indent=2)
        with open(part_path, "w", encoding="utf-8") as fh:
            json.dump(participation, fh, indent=2)

        async with self._make_client() as client:
            await self._send_message_async(
                client,
                f"**Engagement & Participation Ready**\n"
                f"Class: {self._class_name}\n"
                f"Session: `{session_id}`\n"
                f"Date: {date_str}\n\n"
                f"_Provides data for Q2 (engagement) and Q4 (participation / hand raises)_",
            )
            await self._send_file_async(client, eng_path,
                                        "Q2 — Engagement report (talk time, attendance, hand raises)")
            await self._send_file_async(client, part_path,
                                        "Q4 — Per-student participation ranked by hand raises")

        logger.info(f"[Telegram] Packages B+C sent for session {session_id}")

    def send_engagement_package(self, session_id: str, session_dir: str,
                                va_posture_file: str = None):
        asyncio.run(self._engagement_package_coro(session_id, session_dir, va_posture_file))

    # ── Data builders ─────────────────────────────────────────────────────────

    def _build_engagement_data(self, session_id: str, date_str: str,
                                session_dir: str, va_posture_file: str):
        """Assemble engagement and participation dicts from existing session files."""

        # ── Audio stats from transcription.txt ──────────────────────────────
        teacher_pct, student_pct, q_count = 0, 0, 0
        tx_path = os.path.join(session_dir, "transcription.txt")
        if os.path.exists(tx_path):
            teacher_chars = 0
            student_chars = 0
            with open(tx_path, encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    upper = stripped.upper()
                    if upper.startswith("TEACHER:"):
                        teacher_chars += len(stripped)
                    elif "STUDENT" in upper:
                        student_chars += len(stripped)
                        if "?" in stripped:
                            q_count += 1
            total = teacher_chars + student_chars or 1
            teacher_pct = round(teacher_chars / total * 100)
            student_pct = 100 - teacher_pct

        # ── Video stats from front_posture.txt (GVA JSON-lines) ─────────────
        avg_students = 0
        total_hand_raises = 0
        student_raise_counts: dict = {}

        if va_posture_file and os.path.exists(va_posture_file):
            person_counts = []
            try:
                with open(va_posture_file, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            objects = entry.get("objects", [])
                            person_counts.append(len(objects))
                            for obj in objects:
                                sid = str(obj.get("id", "unknown"))
                                label = obj.get("detection", {}).get("label", "")
                                if "raise_up" in label.lower():
                                    student_raise_counts[sid] = (
                                        student_raise_counts.get(sid, 0) + 1
                                    )
                        except (json.JSONDecodeError, KeyError):
                            continue

                avg_students = (
                    int(sum(person_counts) / len(person_counts)) if person_counts else 0
                )
                total_hand_raises = sum(student_raise_counts.values())
            except Exception as exc:
                logger.warning(f"[Telegram] Could not parse posture file: {exc}")

        sorted_students = sorted(
            student_raise_counts.items(), key=lambda x: x[1], reverse=True
        )
        most_active = [sid for sid, _ in sorted_students[:3]]

        engagement = {
            "schema": "smart_classroom_engagement_v1",
            "package": "engagement",
            "session_id": session_id,
            "class_name": self._class_name,
            "date": date_str,
            "openclaw_hints": {
                "Q2_engagement_summary": (
                    "audio.teacher_talk_time_pct shows how much the teacher spoke vs students. "
                    "video.total_hand_raises and video.avg_students_present indicate class energy. "
                    "audio.questions_asked_by_students reflects verbal interaction."
                ),
                "Q4_most_active_students": most_active,
            },
            "audio": {
                "teacher_talk_time_pct":       teacher_pct,
                "student_talk_time_pct":       student_pct,
                "questions_asked_by_students": q_count,
            },
            "video": {
                "avg_students_present": avg_students,
                "total_hand_raises":    total_hand_raises,
                "most_active_students": most_active,
            },
        }

        participation = {
            "schema": "smart_classroom_participation_v1",
            "package": "participation",
            "session_id": session_id,
            "class_name": self._class_name,
            "date": date_str,
            "openclaw_hints": {
                "Q4_participation_ranking": (
                    "students list is sorted by hand_raises descending. "
                    "Use this to identify the most and least active students."
                ),
            },
            "students": [
                {"student_id": sid, "hand_raises": count, "present": True}
                for sid, count in sorted_students
            ],
        }

        return engagement, participation

    # ── Async fire-and-forget wrappers ────────────────────────────────────────

    def send_content_package_async(self, session_id: str, session_dir: str):
        """Non-blocking wrapper — does not delay the API response."""
        threading.Thread(
            target=self.send_content_package,
            args=(session_id, session_dir),
            daemon=True,
        ).start()

    def send_engagement_package_async(self, session_id: str, session_dir: str,
                                      va_posture_file: str = None):
        """Non-blocking wrapper — does not delay the API response."""
        threading.Thread(
            target=self.send_engagement_package,
            args=(session_id, session_dir, va_posture_file),
            daemon=True,
        ).start()


# ── __main__ test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Fill in before running ↓
    API_ID         = 0                          # from my.telegram.org
    API_HASH       = "YOUR_API_HASH_HERE"       # from my.telegram.org
    SESSION_STRING = "YOUR_SESSION_STRING_HERE" # from generate_session.py
    CHAT_ID        = -1001234567890             # group chat id (negative number)
    CLASS_NAME     = "Test Class"

    # Folder that already contains summary.md
    TEST_SESSION_DIR = r"C:\path\to\your\session\output\folder"
    TEST_SESSION_ID  = "test_session_001"

    sender = TelegramSender(API_ID, API_HASH, SESSION_STRING, CHAT_ID, CLASS_NAME)

    print("1. Sending text message...")
    import asyncio
    asyncio.run(sender._content_package_coro(TEST_SESSION_ID, TEST_SESSION_DIR))
    print("   OK")

    summary_path = os.path.join(TEST_SESSION_DIR, "summary.md")
    if not os.path.exists(summary_path):
        print(f"ERROR: summary.md not found at {summary_path}")
        sys.exit(1)

    print("2. Sending summary.md as document...")
    sender._send_file(summary_path, "Lesson summary (test)")
    print("   OK")

    print("3. Sending full Package A (content package)...")
    sender.send_content_package(TEST_SESSION_ID, TEST_SESSION_DIR)
    print("   OK — check your Telegram group")
