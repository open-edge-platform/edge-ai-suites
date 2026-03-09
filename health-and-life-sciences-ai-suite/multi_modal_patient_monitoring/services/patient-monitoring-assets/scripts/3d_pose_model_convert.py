import sys
import tarfile
import urllib.request
from pathlib import Path
import shutil

import yaml
import torch
import openvino as ov


# ----------------------------
# Config-driven model naming
# ----------------------------
CONFIG_PATH = Path("/app/configs/model-config.yaml")


def _load_pose_model_config() -> tuple[str, str, str, str, str]:
    """Load 3D pose model settings from config.

    This function expects /app/configs/model-config.yaml to exist and to
    define pose-3d.models[0] with at least:

      - name
      - target_dir
      - model_url
      - video_dir
      - video_url

    If any of these are missing or the file is not readable, the script
    will raise and fail fast instead of using hardcoded defaults.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"3D pose config not found at {CONFIG_PATH}. Ensure model-config.yaml is mounted."
        )

    try:
        with CONFIG_PATH.open("r") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to parse 3D pose config {CONFIG_PATH}: {e}") from e

    pose_cfg = cfg.get("pose-3d", {})
    models = pose_cfg.get("models", [])
    if not models:
        raise ValueError(
            "model-config.yaml has no pose-3d.models entries; please define at least one."
        )

    first = models[0] or {}
    name = first.get("name")
    target_dir = first.get("target_dir")
    model_url = first.get("model_url")
    video_dir = first.get("video_dir")
    video_url = first.get("video_url")

    if not name or not target_dir or not model_url or not video_dir or not video_url:
        raise ValueError(
            "pose-3d.models[0] must define name, target_dir, model_url, "
            "video_dir, and video_url in model-config.yaml."
        )

    return (
        str(name),
        str(target_dir),
        str(video_dir),
        str(model_url),
        str(video_url),
    )


MODEL_NAME, MODEL_TARGET_DIR, MODEL_VIDEO_DIR, MODEL_URL, VIDEO_URL = _load_pose_model_config()

# Directory where the 3D pose model assets will be stored
# Use the same default as omz-model-download.sh: /models/3d-pose
base_model_dir = Path(MODEL_TARGET_DIR)
base_model_dir.mkdir(parents=True, exist_ok=True)

# Directory where the 3D pose demo video will be stored
videos_dir = Path(MODEL_VIDEO_DIR)
videos_dir.mkdir(parents=True, exist_ok=True)

# Ensure the downloaded OMZ "model" package under /models/3d-pose is importable
if str(base_model_dir) not in sys.path:
    sys.path.insert(0, str(base_model_dir))

# Paths for the original checkpoint archive and extracted .pth
tar_path = base_model_dir / f"{MODEL_NAME}.tar.gz"
ckpt_file = base_model_dir / f"{MODEL_NAME}.pth"

# Final OpenVINO IR path
ov_model_path = base_model_dir / f"{MODEL_NAME}.xml"

# Demo video path
video_path = videos_dir / "face-demographics-walking.mp4"


# 1) Download and extract the .pth checkpoint if needed
if not ckpt_file.exists():
    if not tar_path.exists():
        print(f"Downloading 3D pose checkpoint from {MODEL_URL}")
        urllib.request.urlretrieve(MODEL_URL, tar_path)
        print(f"Saved checkpoint archive to {tar_path}")

    print(f"Extracting checkpoint archive into {base_model_dir}")
    with tarfile.open(tar_path) as f:
        f.extractall(base_model_dir)
    print("Checkpoint extraction complete")


# 1b) Download the demo video if needed
if not video_path.exists():
    print(f"Downloading 3D pose demo video from {VIDEO_URL}")
    # Pexels blocks the default Python user-agent; mimic a browser and
    # send a valid Referer so the request matches typical browser usage.
    req = urllib.request.Request(
        VIDEO_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": "https://www.pexels.com/",
        },
    )
    with urllib.request.urlopen(req) as resp, video_path.open("wb") as out_f:
        shutil.copyfileobj(resp, out_f)
    print(f"Saved 3D pose demo video to {video_path}")


# 2) Convert the PyTorch model to OpenVINO IR if it doesn't already exist
if not ov_model_path.exists():
    from model.with_mobilenet import PoseEstimationWithMobileNet

    pose_estimation_model = PoseEstimationWithMobileNet(is_convertible_by_mo=True)
    pose_estimation_model.load_state_dict(
        torch.load(ckpt_file, map_location="cpu")
    )
    pose_estimation_model.eval()

    with torch.no_grad():
        ov_model = ov.convert_model(
            pose_estimation_model,
            example_input=torch.zeros([1, 3, 256, 448]),
            input=[1, 3, 256, 448],
        )
        ov.save_model(ov_model, ov_model_path)


# 3) Clean up /models/3d-pose so only IR files remain
for item in base_model_dir.iterdir():
    # Keep only top-level .xml and .bin files
    if item.is_file() and item.suffix in {".xml", ".bin"}:
        continue
    if item.is_dir():
        shutil.rmtree(item, ignore_errors=True)
    else:
        try:
            item.unlink()
        except FileNotFoundError:
            pass

print("✅ OpenVINO IR model saved:", ov_model_path)