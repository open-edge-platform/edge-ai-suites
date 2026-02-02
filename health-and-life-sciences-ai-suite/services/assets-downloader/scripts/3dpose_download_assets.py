"""Download and prepare 3D pose assets via Open Model Zoo."""

import subprocess
from pathlib import Path
import requests

MODELS_DIR = Path("/models") / "3d-pose"
VIDEOS_DIR = Path("/videos") / "3d-pose"

MODEL_NAME = "human-pose-estimation-3d-0001"
MODEL_PRECISION = "FP16"

DEMO_VIDEO_URL = (
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/"
    "store-aisle-detection.mp4"
)


def run_cmd(cmd: list) -> None:
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print(f"[✔] Already exists: {dest}")
        return

    print(f"[↓] Downloading: {url}")
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()

    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

    print(f"[✔] Saved: {dest}")


def download_and_convert_model() -> None:
    print("\n=== Downloading & Converting 3D Pose Model ===")

    model_ir_dir = MODELS_DIR / "intel" / MODEL_NAME / MODEL_PRECISION

    xml_file = model_ir_dir / f"{MODEL_NAME}.xml"
    bin_file = model_ir_dir / f"{MODEL_NAME}.bin"

    if xml_file.exists() and bin_file.exists():
        print(f"[✔] IR model already exists: {xml_file}")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    run_cmd([
        "omz_downloader",
        "--name",
        MODEL_NAME,
        "--output_dir",
        str(MODELS_DIR),
        "--cache_dir",
        str(MODELS_DIR / ".cache"),
    ])

    run_cmd([
        "omz_converter",
        "--name",
        MODEL_NAME,
        "--precision",
        MODEL_PRECISION,
        "--download_dir",
        str(MODELS_DIR),
        "--output_dir",
        str(MODELS_DIR),
    ])

    print("[✔] 3D Pose model downloaded and converted to IR")


def download_demo_video() -> None:
    print("\n=== Downloading 3D Pose Demo Video ===")
    video_path = VIDEOS_DIR / "store-aisle-detection.mp4"
    download_file(DEMO_VIDEO_URL, video_path)
    print("[✔] Demo video ready")


def main() -> None:
    print("Starting 3D Pose asset setup...")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    download_and_convert_model()
    download_demo_video()

    print("\n✅ 3D Pose assets ready (IR + video)")


if __name__ == "__main__":
    main()
