"""Convert Ultralytics YOLO weights to an OpenVINO IR at explicit paths.

The rt_info `model_info/model_type=yolo_v11` is mandatory for DL Streamer's
`gvadetect` to pick the correct YOLO post-processing; without it gvadetect
fails with "no suitable model proc".

By default the IR is exported with dynamic=True (any resolution that is a
multiple of 32 works at inference time). For NPU inference use --dynamic False
with --imgsz H W — NPU requires a statically-shaped model.

Usage (from phase2-prototype-demo/):
    # dynamic (default) — CPU/GPU
    python tools/convert_yolo_ov.py --weights models/yolo11n.pt \
        --precision FP16 --xml-path models/yolo11n.xml --bin-path models/yolo11n.bin

    # static 1280x704 for NPU
    python tools/convert_yolo_ov.py --weights models/yolo11n.pt \
        --precision FP16 --xml-path models/yolo11n.xml --bin-path models/yolo11n.bin \
        --dynamic False --imgsz 704 1280
"""

import argparse
import shutil
from pathlib import Path


def convert(weights: str, model_type: str, precision: str, xml_path: Path,
            bin_path: Path, dynamic: bool, imgsz: tuple[int, int] | None):
    from ultralytics import YOLO
    import openvino as ov

    weights_path = Path(weights).resolve()
    if not weights_path.exists():
        raise SystemExit(f"weights not found: {weights_path}")

    if not dynamic:
        if imgsz is None:
            raise SystemExit("--imgsz H W is required when --dynamic False")
        h, w = imgsz
        if h % 32 or w % 32:
            raise SystemExit(f"imgsz must be multiples of 32, got {h}x{w}")

    print(f"[info] loading {weights_path}")
    model = YOLO(str(weights_path))
    model.info()

    export_kwargs: dict = {"format": "openvino", "dynamic": dynamic}
    if not dynamic:
        export_kwargs["imgsz"] = list(imgsz)

    print(f"[info] exporting to OpenVINO IR  {export_kwargs}  (temporary intermediate)")
    exported_dir = Path(model.export(**export_kwargs))
    xml = exported_dir / f"{weights_path.stem}.xml"
    if not xml.exists():
        raise SystemExit(f"exported xml missing: {xml}")

    core = ov.Core()
    ov_model = core.read_model(str(xml))
    ov_model.set_rt_info(model_type, ["model_info", "model_type"])

    xml_path = xml_path.resolve()
    bin_path = bin_path.resolve()
    if xml_path.suffix != ".xml":
        raise SystemExit(f"--xml-path must end in .xml, got: {xml_path}")
    if bin_path.suffix != ".bin":
        raise SystemExit(f"--bin-path must end in .bin, got: {bin_path}")

    xml_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    generated_bin_path = xml_path.with_suffix(".bin")
    ov.save_model(ov_model, str(xml_path), compress_to_fp16=precision == "FP16")
    if generated_bin_path != bin_path:
        generated_bin_path.replace(bin_path)
    print(f"[done] {precision} XML -> {xml_path}")
    print(f"[done] {precision} BIN -> {bin_path}")

    try:
        shutil.rmtree(exported_dir)
    except Exception as e:
        print(f"[warn] could not remove intermediate {exported_dir}: {e}")


def _str2bool(v: str) -> bool:
    if v.lower() in ("true", "1", "yes"):
        return True
    if v.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got {v!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weights", default="tools/yolo11n.pt", help="ultralytics .pt path")
    ap.add_argument("--model-type", default="yolo_v11",
                    help="rt_info model_type (DLS gvadetect uses this to pick post-proc)")
    ap.add_argument("--precision", choices=("FP16", "FP32"), required=True,
                    help="output IR precision")
    ap.add_argument("--xml-path", required=True, help="destination XML path")
    ap.add_argument("--bin-path", required=True, help="destination BIN path")
    ap.add_argument("--dynamic", type=_str2bool, default=True,
                    help="export with dynamic shapes (default True); use False for NPU")
    ap.add_argument("--imgsz", type=int, nargs=2, metavar=("H", "W"), default=None,
                    help="static input shape H W (multiples of 32); required if --dynamic False")
    args = ap.parse_args()
    imgsz = tuple(args.imgsz) if args.imgsz else None
    convert(args.weights, args.model_type, args.precision, Path(args.xml_path),
            Path(args.bin_path), args.dynamic, imgsz)


if __name__ == "__main__":
    main()
