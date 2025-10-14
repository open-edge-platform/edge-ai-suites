import os
from pathlib import Path
from typing import Optional, Literal, Dict, Any

def get_or_download_model_dir(
    model: str,
    hub: Literal["hf", "ms"] = "ms",
    revision: Optional[str] = None,
    local_dir: Optional[str] = None,
    exist_ok: bool = True,
    **snapshot_kwargs: Any,
) -> str:
    """
    Ensure a model snapshot is present locally and return its directory.

    Args:
        model: Repo/model id or local path.
        hub: "hf" (Hugging Face) or "ms" (ModelScope).
        revision: Optional revision / branch / commit.
        local_dir: Preferred target directory. If it exists and exist_ok=True, it is returned.
        exist_ok: If False and local_dir exists but is empty/invalid, re-download.
        **snapshot_kwargs: Passed through to underlying snapshot_download.

    Returns:
        Absolute path to directory containing model files.
    """
    # If user already supplies an existing directory with files, just return it.
    if local_dir and os.path.isdir(local_dir):
        # Basic heuristic: if it has at least one file, trust it.
        if exist_ok and any(Path(local_dir).iterdir()):
            return str(Path(local_dir).resolve())

    # Select snapshot_download implementation
    if hub == "hf":
        try:
            from huggingface_hub import snapshot_download
        except ImportError as e:
            raise RuntimeError("huggingface_hub not installed") from e
        download = snapshot_download
        kwargs: Dict[str, Any] = {}
        if revision:
            kwargs["revision"] = revision
        if local_dir:
            kwargs["local_dir"] = local_dir
    elif hub == "ms":
        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except ImportError as e:
            raise RuntimeError("modelscope not installed") from e
        download = snapshot_download
        kwargs = {}
        if revision:
            kwargs["revision"] = revision
        if local_dir:
            kwargs["local_dir"] = local_dir
    else:
        raise ValueError(f"Unsupported hub: {hub}")

    # Merge extra kwargs (user can override)
    kwargs.update(snapshot_kwargs)

    # If model is already a local path and exists, just return it (even if not downloaded via hub)
    if os.path.isdir(model) and not kwargs.get("local_dir"):
        return str(Path(model).resolve())

    # Perform (or reuse) download
    model_dir = download(model, **kwargs)

    return str(Path(model_dir).resolve())