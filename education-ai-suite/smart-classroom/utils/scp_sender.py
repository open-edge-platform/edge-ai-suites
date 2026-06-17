"""
scp_sender.py
-------------
Sends session data packages to a remote Linux machine via SCP (OpenSSH).

Used as an alternative to telegram_sender when the Windows machine cannot
reach Telegram's MTProto servers (e.g. corporate proxy filtering raw IPs).

Package A  (sent after content-segmentation completes)
    Files: session_meta.json, summary.md, topics.json
  Answers: Q1 (topics covered) and Q3 (absentee catch-up)

Package B  (sent when VA pipeline stops)
    Files: engagement_report.json
  Answers: Q2 (engagement) and Q4 (most active students)

Activation: set  scp_sender.enabled: true  in config.yaml.

Requirements:
  • OpenSSH client installed (scp / ssh executables on PATH)
  • Windows machine's public key added to ~/.ssh/authorized_keys on the
    remote Linux machine (so no password prompt appears)
  • SSH host alias configured in ~/.ssh/config  OR  host/user in config.yaml
"""

import json
import logging
import os
import subprocess
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# Full paths to OpenSSH executables — avoids PATH lookup failures in subprocess
_SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"
_SCP = r"C:\Windows\System32\OpenSSH\scp.exe"


# ── Standalone file writer (no sender required) ────────────────────────────────

def write_engagement_reports(session_id: str, session_dir: str, va_stats: dict) -> tuple:
    """
    Write engagement_report.json into session_dir.
    Runs only when scp_sender is enabled in config.
    Returns eng_path on success, None on failure.
    """
    try:
        from utils.config_loader import config as _cfg
        scp_cfg = getattr(_cfg, "scp_sender", None)
        if not (scp_cfg and getattr(scp_cfg, "enabled", False)):
            logger.info("[Reports] scp_sender disabled; skipping engagement_report generation.")
            return None, None
        class_name = getattr(getattr(_cfg, "scp_sender", None), "class_name",
                             getattr(getattr(_cfg, "telegram", None), "class_name", "Smart Classroom"))
    except Exception:
        class_name = "Smart Classroom"

    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        va_stats = va_stats or {}

        # ── Audio stats ───────────────────────────────────────────────────────
        teacher_pct, student_pct, q_count = 0, 0, 0
        tx_path = os.path.join(session_dir, "transcription.txt")
        if os.path.exists(tx_path):
            teacher_chars = student_chars = 0
            with open(tx_path, encoding="utf-8") as fh:
                for line in fh:
                    s = line.strip()
                    u = s.upper()
                    if u.startswith("TEACHER:"):
                        teacher_chars += len(s)
                    elif "STUDENT" in u:
                        student_chars += len(s)
                        if "?" in s:
                            q_count += 1
            total = teacher_chars + student_chars or 1
            teacher_pct = round(teacher_chars / total * 100)
            student_pct = 100 - teacher_pct

        # ── Video stats from get_pose_stats() result ──────────────────────────
        avg_students      = va_stats.get("student_count", 0)
        total_hand_raises = va_stats.get("raise_up_count", 0)
        raise_reid        = va_stats.get("raise_reid", [])
        most_active       = [str(e["student_id"]) for e in raise_reid[:3]]

        engagement = {
            "schema": "smart_classroom_engagement_v1",
            "package": "engagement",
            "session_id": session_id,
            "class_name": class_name,
            "date": date_str,
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

        os.makedirs(session_dir, exist_ok=True)
        eng_path  = os.path.join(session_dir, "engagement_report.json")
        with open(eng_path,  "w", encoding="utf-8") as fh:
            json.dump(engagement, fh, indent=2)

        logger.info(f"[Reports] Written: {eng_path}")
        return eng_path, None

    except Exception as exc:
        logger.error(f"[Reports] Failed to write engagement reports: {exc}", exc_info=True)
        return None, None


# ── Singleton ──────────────────────────────────────────────────────────────────

_sender_instance = None


def get_scp_sender():
    """Return the configured SCPSender singleton, or None if disabled."""
    global _sender_instance
    if _sender_instance is not None:
        return _sender_instance
    try:
        from utils.config_loader import config  # lazy import avoids circular refs
        cfg = getattr(config, "scp_sender", None)
        if cfg and getattr(cfg, "enabled", False):
            _sender_instance = SCPSender(
                host=str(cfg.host),
                identity_file=getattr(cfg, "identity_file", "") or "",
                remote_base_path=str(cfg.remote_base_path),
                class_name=getattr(cfg, "class_name", "Smart Classroom"),
            )
            logger.info("[SCP] Sender initialised.")
    except Exception as exc:
        logger.error(f"[SCP] Failed to initialise sender: {exc}")
    return _sender_instance


# ── Core class ─────────────────────────────────────────────────────────────────

class SCPSender:
    def __init__(self, host: str, identity_file: str,
                 remote_base_path: str, class_name: str):
        self._host = host
        self._identity_file = identity_file
        self._remote_base_path = remote_base_path.rstrip("/")
        self._class_name = class_name

    # ── Subprocess helpers ─────────────────────────────────────────────────────

    def _remote_host(self) -> str:
        """Return the SSH host alias or IP (user resolved by ~/.ssh/config)."""
        return self._host

    def _ssh_options(self) -> list:
        """Common SSH options shared by both ssh and scp commands."""
        opts = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
        if self._identity_file:
            opts = ["-i", self._identity_file] + opts
        return opts

    def _run(self, cmd: list, description: str) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error(
                    f"[SCP] {description} failed (rc={result.returncode}): "
                    f"{result.stderr.strip()}"
                )
                return False
            else:
                logger.info(f"[SCP] {description} succeeded.")
                return True
        except subprocess.TimeoutExpired:
            logger.error(f"[SCP] {description} timed out after 120 s.")
            return False
        except FileNotFoundError:
            logger.error(
                f"[SCP] ssh/scp executable not found at {_SSH}. "
                "Ensure the OpenSSH client is installed (Windows optional feature)."
            )
            return False
        except Exception as exc:
            logger.error(f"[SCP] {description} error: {exc}")
            return False

    def _mkdir_remote(self, remote_dir: str) -> bool:
        """Create the session directory on the remote host."""
        cmd = [_SSH] + self._ssh_options() + [
            self._remote_host(), f"mkdir -p '{remote_dir}'"
        ]
        return self._run(cmd, f"mkdir -p {remote_dir}")

    def _copy_files(self, local_files: list, remote_dir: str) -> bool:
        """SCP a list of local files to remote_dir/. Missing files are skipped."""
        existing = [f for f in local_files if os.path.exists(f)]
        missing  = set(local_files) - set(existing)
        for f in missing:
            logger.warning(f"[SCP] File not found, skipping: {f}")
        if not existing:
            logger.warning("[SCP] No files to copy.")
            return False
        cmd = (
            [_SCP]
            + self._ssh_options()
            + existing
            + [f"{self._remote_host()}:{remote_dir}/"]
        )
        return self._run(cmd, f"copy {len(existing)} file(s) → {remote_dir}/")

    # ── Package A — Session Content ────────────────────────────────────────────

    def send_content_package(self, session_id: str, session_dir: str):
        """Build session_meta.json then SCP Package A content files to the remote host."""

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
                "topics": "topics.json",
            },
            "openclaw_hints": {
                "Q1_topics_covered": (
                    "Read topics.json for the timestamped list; "
                    "read ## Session Outline in summary.md for human-readable form."
                ),
                "Q3_absentee_catchup": (
                    "summary.md contains the full lesson content. "
                    "topics.json gives a timed breakdown the student can use for self-study."
                ),
            },
        }

        meta_path = os.path.join(session_dir, "session_meta.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        remote_dir = f"{self._remote_base_path}/{session_id}"
        if not self._mkdir_remote(remote_dir):
            logger.error(f"[SCP] Package A failed for session {session_id} (remote dir creation failed).")
            return

        files = [
            os.path.join(session_dir, fname)
            for fname in ("session_meta.json", "summary.md", "topics.json")
        ]
        if self._copy_files(files, remote_dir):
            logger.info(f"[SCP] Package A sent for session {session_id}")
        else:
            logger.error(f"[SCP] Package A failed for session {session_id} (file copy failed).")

    def send_content_package_async(self, session_id: str, session_dir: str):
        """Non-blocking wrapper — does not delay the API response."""
        threading.Thread(
            target=self.send_content_package,
            args=(session_id, session_dir),
            daemon=True,
        ).start()

    # ── Package B — Engagement ───────────────────────────────────────────────

    def send_engagement_package(self, session_id: str, session_dir: str,
                                va_stats: dict = None):
        """Write engagement_report.json (via write_engagement_reports) then SCP it."""
        eng_path, _ = write_engagement_reports(session_id, session_dir, va_stats)
        if not eng_path:
            logger.error("[SCP] Skipping SCP send — report writing failed.")
            return

        remote_dir = f"{self._remote_base_path}/{session_id}"
        if not self._mkdir_remote(remote_dir):
            logger.error(f"[SCP] Package B failed for session {session_id} (remote dir creation failed).")
            return
        if self._copy_files([eng_path], remote_dir):
            logger.info(f"[SCP] Package B sent for session {session_id}")
        else:
            logger.error(f"[SCP] Package B failed for session {session_id} (file copy failed).")

    def send_engagement_package_async(self, session_id: str, session_dir: str,
                                      va_stats: dict = None):
        """Non-blocking wrapper — does not delay the API response."""
        threading.Thread(
            target=self.send_engagement_package,
            args=(session_id, session_dir, va_stats),
            daemon=True,
        ).start()

    # ── Engagement data builder ────────────────────────────────────────────────

    def _build_engagement_data(self, session_id: str, date_str: str,
                                session_dir: str, va_stats: dict):
        """Assemble the engagement dict.

        va_stats: the dict returned by VideoAnalyticsPipelineService.get_pose_stats()
            {
              'student_count': int,
              'stand_count':   int,
              'raise_up_count': int,
              'stand_reid':    [{student_id, count}, ...],
              'raise_reid':    [{student_id, count}, ...],  # sorted desc by count
            }
        """
        # ── Audio stats from transcription.txt ────────────────────────────────
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

        # ── Video stats from pre-computed get_pose_stats() result ─────────────
        # Uses the same state-machine engine as the /class-statistics UI endpoint
        # so report values are consistent with what was shown live.
        va_stats = va_stats or {}
        avg_students     = va_stats.get("student_count", 0)
        total_hand_raises = va_stats.get("raise_up_count", 0)
        raise_reid       = va_stats.get("raise_reid", [])   # [{student_id, count}] sorted desc
        most_active      = [str(entry["student_id"]) for entry in raise_reid[:3]]

        engagement = {
            "schema": "smart_classroom_engagement_v1",
            "package": "engagement",
            "session_id": session_id,
            "class_name": self._class_name,
            "date": date_str,
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

        return engagement
