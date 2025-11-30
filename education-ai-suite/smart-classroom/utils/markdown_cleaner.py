import re

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
