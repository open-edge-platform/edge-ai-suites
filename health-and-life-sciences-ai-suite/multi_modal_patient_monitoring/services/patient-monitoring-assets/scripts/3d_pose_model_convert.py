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


def _load_pose_model_config() -> tuple[str, str, str]:
    """Load 3D pose model name, target_dir, and video_dir from config.

    This function expects /app/configs/model-config.yaml to exist and to
    define pose-3d.models[0] with at least name, target_dir, and
    video_dir. If any of these are missing or the file is not readable,
    the script will raise and fail fast instead of using hardcoded
    defaults.
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
    video_dir = first.get("video_dir")

    if not name or not target_dir or not video_dir:
        raise ValueError(
            "pose-3d.models[0] must define name, target_dir, and video_dir in model-config.yaml."
        )

    return str(name), str(target_dir), str(video_dir)


MODEL_NAME, MODEL_TARGET_DIR, MODEL_VIDEO_DIR = _load_pose_model_config()

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
video_url = "https://storage.openvinotoolkit.org/data/test_data/videos/face-demographics-walking.mp4"
video_path = videos_dir / "face-demographics-walking.mp4"


# 1) Download and extract the .pth checkpoint if needed
if not ckpt_file.exists():
    # URL still points to the default OMZ model; MODEL_NAME controls
    # the local file naming via config.
    url = (
        "https://storage.openvinotoolkit.org/repositories/open_model_zoo/public/2022.1/"
        "human-pose-estimation-3d-0001/human-pose-estimation-3d.tar.gz"
    )

    if not tar_path.exists():
        print(f"Downloading 3D pose checkpoint from {url}")
        urllib.request.urlretrieve(url, tar_path)
        print(f"Saved checkpoint archive to {tar_path}")

    print(f"Extracting checkpoint archive into {base_model_dir}")
    with tarfile.open(tar_path) as f:
        f.extractall(base_model_dir)
    print("Checkpoint extraction complete")


# 1b) Download the demo video if needed
if not video_path.exists():
    print(f"Downloading 3D pose demo video from {video_url}")
    urllib.request.urlretrieve(video_url, video_path)
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
