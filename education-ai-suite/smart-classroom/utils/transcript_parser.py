# utils/transcript_parser.py
"""Simple transcript parsing utilities - no heavy dependencies."""

import re

_timestamp_pattern = re.compile(r"\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]\s*(.*)")


def parse_transcript_lines(transcript_text: str) -> list:
    """Parse a timestamped transcript into a list of {start, end, text} dicts."""
    lines = []
    for raw_line in transcript_text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        match = _timestamp_pattern.match(raw_line)
        if match:
            lines.append({
                "start": float(match.group(1)),
                "end": float(match.group(2)),
                "text": match.group(3),
            })
    return lines


def build_topic_text(topic: dict, transcript_lines: list) -> str:
    """Extract the transcript text that falls within a topic's time range."""
    start_time = topic["start_time"]
    end_time = topic["end_time"]
    
    chunks = []
    for line in transcript_lines:
        # Include lines that overlap with [start_time, end_time]
        if line["end"] < start_time:
            continue
        if line["start"] > end_time:
            break
        chunks.append(line["text"])
    
    return " ".join(chunks)
