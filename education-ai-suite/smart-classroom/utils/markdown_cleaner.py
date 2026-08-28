import re

# Matches a complete <think>...</think> reasoning block (non-greedy, multiline).
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
# Matches stray think tags and chat special tokens like <|im_start|>, <|im_end|>, <|endoftext|>.
_SPECIAL_TOKEN_RE = re.compile(r"</?think>|<\|[^|]*\|>", re.IGNORECASE)
_OPEN_THINK_RE = re.compile(r"<think>", re.IGNORECASE)
_CLOSE_THINK_RE = re.compile(r"</think>", re.IGNORECASE)


def _strip_prefilled_think(text: str) -> str:
    """Drop a reasoning block whose opening <think> came from the prompt.

    When thinking is on, the Qwen3.x chat templates append a bare "<think>\\n"
    to the generation prompt, so generated text starts *inside* the block and
    carries only the closing tag. Everything up to the first </think> is
    therefore reasoning -- unless a <think> opens before it, which is the
    ordinary self-contained case _THINK_BLOCK_RE already handles.

    A block that is never closed (generation truncated mid-reasoning by
    max_new_tokens) is left untouched: there is no answer to recover, and
    returning the raw text keeps the failure visible to the caller.
    """
    close = _CLOSE_THINK_RE.search(text)
    if close is None:
        return text
    opening = _OPEN_THINK_RE.search(text)
    if opening is not None and opening.start() < close.start():
        return text
    return text[close.end():]


def strip_think_tokens(text: str) -> str:
    """Remove <think>...</think> reasoning blocks and any leftover special tokens."""
    if not text:
        return text or ""
    text = _strip_prefilled_think(text)
    text = _THINK_BLOCK_RE.sub("", text)
    text = _SPECIAL_TOKEN_RE.sub("", text)
    return text.strip()


_THINK_TAGS = ("<think>", "</think>")
_MAX_TAG_LEN = max(len(tag) for tag in _THINK_TAGS)


class StreamThinkFilter:
    """Stateful filter that strips <think>...</think> blocks and special tokens
    from a token stream, preserving state across token boundaries.

    Pass ``in_think=True`` when the prompt's chat template already emitted the
    opening <think> (see :func:`utils.reasoning.thinking_enabled`): the stream
    then carries only the closing tag, and a filter that started outside the
    block would leak the whole reasoning pass into the output.

    A tag can arrive split across two chunks ("</thi" + "nk>"), so any trailing
    text that is still a viable prefix of a tag is withheld until the next
    chunk resolves it. Call :meth:`flush` once the stream ends to release a
    withheld tail that never turned out to be a tag.
    """

    def __init__(self, in_think: bool = False):
        self.in_think = in_think
        self._pending = ""

    @staticmethod
    def _partial_tag_len(text: str) -> int:
        """Length of the trailing run of ``text`` that could still become a tag."""
        for n in range(min(len(text), _MAX_TAG_LEN - 1), 0, -1):
            suffix = text[-n:]
            if any(tag.startswith(suffix) for tag in _THINK_TAGS):
                return n
        return 0

    def filter(self, text: str) -> str:
        if not text:
            return ""
        buffer = self._pending + text
        self._pending = ""
        out = []
        i = 0
        while i < len(buffer):
            if not self.in_think:
                start = buffer.find("<think>", i)
                if start == -1:
                    held = self._partial_tag_len(buffer[i:])
                    end = len(buffer) - held
                    out.append(buffer[i:end])
                    self._pending = buffer[end:]
                    break
                out.append(buffer[i:start])
                self.in_think = True
                i = start + len("<think>")
            else:
                end = buffer.find("</think>", i)
                if end == -1:
                    # Remainder is inside the think block; drop it, but keep a
                    # possible split closing tag for the next chunk.
                    held = self._partial_tag_len(buffer[i:])
                    self._pending = buffer[len(buffer) - held:] if held else ""
                    break
                self.in_think = False
                i = end + len("</think>")
        return _SPECIAL_TOKEN_RE.sub("", "".join(out))

    def flush(self) -> str:
        """Release any withheld tail; call once the token stream is exhausted."""
        pending, self._pending = self._pending, ""
        if self.in_think or not pending:
            return ""
        return _SPECIAL_TOKEN_RE.sub("", pending)


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
