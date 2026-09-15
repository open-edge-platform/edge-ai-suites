import os
from functools import lru_cache

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


@lru_cache(maxsize=None)
def load_prompt(*parts: str) -> str:
    """Read and cache a prompt file at prompts/<parts[0]>/.../<parts[-1]>.txt."""
    path = os.path.join(_PROMPTS_DIR, *parts) + ".txt"
    with open(path, "r", encoding="utf-8") as f:
        return f.read().rstrip("\n")
