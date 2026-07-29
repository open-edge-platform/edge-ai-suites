import re

# Matches a complete <think>...</think> reasoning block (non-greedy, multiline).
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
# Matches stray think tags and chat special tokens like <|im_start|>, <|im_end|>, <|endoftext|>.
_SPECIAL_TOKEN_RE = re.compile(r"</?think>|<\|[^|]*\|>", re.IGNORECASE)


def strip_think_tokens(text: str) -> str:
    """Remove <think>...</think> reasoning blocks and any leftover special tokens."""
    if not text:
        return text or ""
    text = _THINK_BLOCK_RE.sub("", text)
    text = _SPECIAL_TOKEN_RE.sub("", text)
    return text.strip()


class StreamThinkFilter:
    """Stateful filter that strips <think>...</think> blocks and special tokens
    from a token stream, preserving state across token boundaries."""

    def __init__(self):
        self.in_think = False

    def filter(self, text: str) -> str:
        if not text:
            return ""
        out = []
        i = 0
        while i < len(text):
            if not self.in_think:
                start = text.find("<think>", i)
                if start == -1:
                    out.append(text[i:])
                    break
                out.append(text[i:start])
                self.in_think = True
                i = start + len("<think>")
            else:
                end = text.find("</think>", i)
                if end == -1:
                    # Remainder is inside the think block; drop it.
                    break
                self.in_think = False
                i = end + len("</think>")
        return _SPECIAL_TOKEN_RE.sub("", "".join(out))


def markdown_to_plain(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^>\s*", "", text, flags=re.M)
    text = re.sub(r"^-{3,}$", "", text, flags=re.M)
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()
