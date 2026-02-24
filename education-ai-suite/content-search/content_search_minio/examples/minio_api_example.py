"""MinIO standard API usage example.

This is a reference program showing the typical way other services should use
`minio_client.py`.

Pattern:
1) Create a `MinioStore` once at startup
2) Ensure bucket exists
3) Use `put_json/get_json` and `put_bytes/get_bytes` for app data
3b) Use `put_file/get_file` for local file upload/download
4) Demonstrate run_id for raw/derived keys
5) Use `object_exists/list_object_names` for checks
6) Demonstrate deletes (`delete_object`, `delete_prefix`) for cleanup

Config:
- Read from ./config.json (same directory as minio_client.py)
- Must include: minio.server, minio.root_user, minio.root_password, minio.bucket

Run (from this folder):
    python examples/minio_api_example.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_search_minio.minio_client import MinioStore


def rel_chunk_summary(*, chunk_index: int) -> str:
    return f"chunksum-v1/summaries/chunk_{chunk_index:04d}/summary.txt"


def rel_frame_image(*, chunk_index: int, frame_index: int, ext: str = "jpeg") -> str:
    return f"frames-v1/frames/chunk_{chunk_index:04d}/frame_{frame_index:06d}.{ext}"


def run_demo() -> None:
    # Create the standard store from config.json.
    store = MinioStore.from_config()
    print(f"Using bucket: {store.bucket}")


    # Use a unique run_id so this script is safe to run repeatedly: runs/{run_id}/...
    run_id = f"demo_{int(time.time())}"
    run_prefix = f"runs/{run_id}/"

    # 1) Ensure bucket exists.
    store.ensure_bucket()

    # Optional: list buckets visible to these credentials.
    try:
        print(f"Buckets: {store.list_buckets()}")
    except Exception as e:
        print(f"list_buckets() failed (may be restricted by policy): {e}")

    # 2) JSON write/read
    json_key = f"{run_prefix}app/hello.json"
    store.put_json(json_key, {"hello": "world"}, ensure_ascii=False, indent=2)
    back = store.get_json(json_key)
    print("JSON read back:")
    print(json.dumps(back, ensure_ascii=False, indent=2))

    # 3) Bytes example (upload + download)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        local_in = tmp / "hello.txt"
        local_out = tmp / "hello_downloaded.txt"

        local_in.write_text("hello from MinioStore.put_bytes()\n", encoding="utf-8")

        obj_key = f"{run_prefix}app/hello.txt"
        data = local_in.read_bytes()
        store.put_bytes(obj_key, data, content_type="text/plain")

        downloaded = store.get_bytes(obj_key)
        local_out.write_bytes(downloaded)
        print("Downloaded text:")
        print(local_out.read_text(encoding="utf-8").strip())

        # 3b) File upload/download example (put_file/get_file)
        local_upload = tmp / "upload_me.bin"
        local_download = tmp / "upload_me_downloaded.bin"

        local_upload.write_bytes(b"\x00\x01\x02demo file via put_file\n")
        file_key = f"{run_prefix}app/upload_me.bin"

        store.put_file(file_key, local_upload)
        store.get_file(file_key, local_download)
        print(f"File roundtrip OK? {local_download.read_bytes() == local_upload.read_bytes()}")

    # 4) run_id keys (raw / derived)
    asset_type = "video"  # could be: video | image | doc
    asset_id = "asset_001"

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        raw_local = td / "raw_input.txt"
        raw_local.write_text("hello raw for this run\n", encoding="utf-8")

        raw_object = MinioStore.build_raw_object_key(run_id, asset_type, asset_id, raw_local.name)
        store.put_file(raw_object, raw_local, content_type="text/plain")

    chunk_index = 3
    summary_object = MinioStore.build_derived_object_key(
        run_id,
        asset_type,
        asset_id,
        rel_chunk_summary(chunk_index=chunk_index),
    )
    store.put_bytes(
        summary_object,
        f"summary for chunk {chunk_index}\n".encode("utf-8"),
        content_type="text/plain",
    )

    frame_object = MinioStore.build_derived_object_key(
        run_id,
        asset_type,
        asset_id,
        rel_frame_image(chunk_index=chunk_index, frame_index=120),
    )
    store.put_bytes(frame_object, b"\xff\xd8\xff\xd9", content_type="image/jpeg")

    print(f"Uploaded run objects under runs/{run_id}/...")

    # 5) object_exists/list_object_names checks
    print(f"Exists {json_key}? {store.object_exists(json_key)}")
    print(f"List under {run_prefix}:")
    for key in store.list_object_names(run_prefix):
        print(f"- {key}")

    # 6) delete examples
    delete_me_key = f"{run_prefix}tmp/delete_me.txt"
    store.put_bytes(delete_me_key, b"delete me", content_type="text/plain")
    print(f"Exists {delete_me_key} before delete? {store.object_exists(delete_me_key)}")
    store.delete_object(delete_me_key)
    print(f"Exists {delete_me_key} after delete? {store.object_exists(delete_me_key)}")

    deleted_run = store.delete_prefix(run_prefix)
    print(f"Deleted under {run_prefix}: {deleted_run} objects")


if __name__ == "__main__":
    run_demo()
