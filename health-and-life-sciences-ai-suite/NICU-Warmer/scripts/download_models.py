#!/usr/bin/env python3
"""NICU Warmer — Config-driven model & asset downloader.

Reads model-config.yaml and downloads pre-converted OpenVINO IR models
and demo video from specified URLs. Idempotent: skips files that already
exist and pass size validation.

Usage:
    python download_models.py --config /app/model-config.yaml --output /models
"""

import argparse
import hashlib
import os
import ssl
import sys
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML required. Install with: pip install pyyaml")


def _make_opener():
    """Create URL opener with proxy support from environment."""
    proxy_handler = urllib.request.ProxyHandler()
    return urllib.request.build_opener(proxy_handler)


def download_file(url: str, dest: Path, description: str = "") -> bool:
    """Download a file if it doesn't already exist.

    Returns True if downloaded, False if skipped (already exists).
    """
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size} bytes)")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    label = description or dest.name
    print(f"  [GET]  {label}")
    print(f"         {url}")

    # Create SSL context that respects system certs
    ctx = ssl.create_default_context()
    # Allow fallback for corporate proxies with custom CAs
    if os.environ.get("NICU_ALLOW_INSECURE_DOWNLOAD"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    opener = _make_opener()
    req = urllib.request.Request(url, headers={"User-Agent": "nicu-model-downloader/1.0"})

    try:
        with urllib.request.urlopen(req, context=ctx) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 64 * 1024
            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    print(f"\r         {downloaded // 1024}KB / {total // 1024}KB ({pct}%)", end="", flush=True)
            print()  # newline after progress
    except Exception as e:
        # Clean up partial download
        if dest.exists():
            dest.unlink()
        print(f"  [FAIL] {label}: {e}", file=sys.stderr)
        return False

    print(f"  [OK]   {dest.name} ({dest.stat().st_size} bytes)")
    return True


def process_model_group(group: dict, output_dir: Path) -> int:
    """Process a model group from config. Returns number of failures."""
    failures = 0
    # target_dir in config uses container paths (/models, /data).
    # When running on host, remap to output_dir-relative paths.
    raw_target = group.get("target_dir", "")
    if raw_target.startswith("/"):
        # Strip leading container path prefix, make relative to output_dir
        # /models/rppg -> <output_dir>/models_rppg
        # /models/action/FP32 -> <output_dir>/model_artifacts/action/FP32  (no — keep simple)
        # /models -> <output_dir> (root level models go in project root)
        # /data -> <output_dir>
        rel = raw_target.lstrip("/")
        if rel == "models" or rel == "data":
            target = output_dir
        elif rel.startswith("models/rppg"):
            target = output_dir / "models_rppg"
        elif rel.startswith("models/action"):
            target = output_dir / rel.replace("models/action", "model_artifacts/action", 1)
        else:
            target = output_dir / rel
    else:
        target = output_dir / raw_target if raw_target else output_dir

    for model in group.get("models", []):
        name = model.get("name", "unknown")

        # Standard IR model (xml + bin pair)
        if "xml_url" in model and "bin_url" in model:
            xml_dest = target / f"{name}.xml"
            bin_dest = target / f"{name}.bin"
            if not download_file(model["xml_url"], xml_dest, f"{name} (xml)"):
                pass  # skip is not a failure
            elif xml_dest.exists():
                pass
            else:
                failures += 1
            if not download_file(model["bin_url"], bin_dest, f"{name} (bin)"):
                pass
            elif bin_dest.exists():
                pass
            else:
                failures += 1

        # Single-file download (video, hdf5, etc.)
        elif "url" in model:
            ext = Path(model["url"]).suffix or ""
            dest = target / f"{name}{ext}"
            if not download_file(model["url"], dest, name):
                pass
            elif dest.exists():
                pass
            else:
                failures += 1

        # HDF5 model that needs conversion
        elif "hdf5_url" in model:
            hdf5_dest = target / f"{name}.hdf5"
            if not download_file(model["hdf5_url"], hdf5_dest, f"{name} (hdf5)"):
                pass
            elif hdf5_dest.exists():
                pass
            else:
                failures += 1

    return failures


def main():
    parser = argparse.ArgumentParser(description="NICU model downloader")
    parser.add_argument("--config", default="/app/model-config.yaml",
                        help="Path to model-config.yaml")
    parser.add_argument("--output", default="/models",
                        help="Default output directory")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_failures = 0
    for group_name, group_data in config.items():
        if not isinstance(group_data, dict) or "models" not in group_data:
            continue
        print(f"\n{'='*60}")
        print(f"  {group_name}: {group_data.get('description', '')}")
        print(f"{'='*60}")
        total_failures += process_model_group(group_data, output_dir)

    print(f"\n{'='*60}")
    if total_failures == 0:
        print("  All models downloaded successfully.")
    else:
        print(f"  WARNING: {total_failures} download(s) failed.")
    print(f"{'='*60}")
    sys.exit(1 if total_failures > 0 else 0)


if __name__ == "__main__":
    main()
