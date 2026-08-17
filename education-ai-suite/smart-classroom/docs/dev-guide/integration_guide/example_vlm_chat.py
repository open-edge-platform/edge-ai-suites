import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8000/v1/chat/completions"


def _image_url(source: str) -> str:
    if source.startswith("data:"):
        return source
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=60) as resp:
            data = resp.read()
            mime = resp.headers.get_content_type() or "image/jpeg"
    else:
        with open(source, "rb") as f:
            data = f.read()
        mime = mimetypes.guess_type(source)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _build_messages(prompt: str, images: list[str]):
    if not images:
        return [{"role": "user", "content": prompt}]
    content = [{"type": "text", "text": prompt}]
    content += [
        {"type": "image_url", "image_url": {"url": _image_url(p)}} for p in images
    ]
    return [{"role": "user", "content": content}]


def _post(url: str, payload: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=600)


def _run_non_stream(resp):
    data = json.loads(resp.read().decode("utf-8"))
    print(data["choices"][0]["message"]["content"])


def _run_stream(resp):
    for raw in resp:
        line = raw.decode("utf-8")
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if chunk == "[DONE]":
            break
        try:
            delta = json.loads(chunk)["choices"][0]["delta"].get("content")
        except (KeyError, IndexError, json.JSONDecodeError):
            delta = None
        if delta:
            print(delta, end="", flush=True)
    print()


def _as_curl(url: str, payload: dict) -> str:
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    return (
        f"curl --location '{url}' \\\n"
        f"--header 'Content-Type: application/json' \\\n"
        f"--data '{body}'"
    )


def main():
    ap = argparse.ArgumentParser(description="Call the Smart Classroom LLM / VLM endpoint")
    ap.add_argument("prompt", help="text prompt")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("-i", "--image", action="append", default=[],
                    help="image path or URL; repeat for multiple (VLM mode)")
    ap.add_argument("--stream", action="store_true", help="stream tokens (SSE)")
    ap.add_argument("--max-tokens", type=int, default=5120)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--no-thinking", action="store_true",
                    help="set enable_thinking=false (suppress Qwen3 thinking)")
    args = ap.parse_args()

    payload = {
        "messages": _build_messages(args.prompt, args.image),
        "max_completion_tokens": args.max_tokens,
        "stream": args.stream,
    }
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.no_thinking:
        payload["enable_thinking"] = False

    print("Equivalent curl command:\n")
    print(_as_curl(args.url, payload))
    print("\nResponse:")

    try:
        resp = _post(args.url, payload)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"Connection failed: {e}")

    if args.stream:
        _run_stream(resp)
    else:
        _run_non_stream(resp)


if __name__ == "__main__":
    main()
