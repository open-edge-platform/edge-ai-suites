from pathlib import Path
import time
import os
import json
import yaml
import cv2
import numpy as np
import openvino as ov
from PIL import Image, ImageDraw, ImageFont


class LayoutDetectorV3:
    """PP-DocLayoutV3 document layout detection using an OpenVINO IR
    converted via paddle2onnx.

    Model interface (3 inputs / 3 outputs):
      inputs : image [N,3,800,800], scale_factor [N,2], im_shape [N,2]
      outputs: fetch_name_0 [K,7] = [cls_id, score, x1, y1, x2, y2, _]
               fetch_name_1 [1]   = valid detection count
               fetch_name_2 [K,200,200] = instance masks (unused here)
    """

    INPUT_SIZE = 800

    LABEL_LIST = [
        "abstract", "algorithm", "aside_text", "chart", "content", "display_formula",
        "doc_title", "figure_title", "footer", "footer_image", "footnote", "formula_number",
        "header", "header_image", "image", "inline_formula", "number", "paragraph_title",
        "reference", "reference_content", "seal", "table", "text", "vertical_text", "vision_footnote"
    ]

    def __init__(self, model_path, device="GPU", threshold=0.5):
        self.model_path = Path(model_path)
        self.device = device
        self.threshold = threshold
        self.inference_times = []

        model_file = self._resolve_model_file()
        print(f"Loading PP-DocLayoutV3 from {model_file} on {device}...")
        load_start = time.time()

        self.core = ov.Core()
        model = self.core.read_model(str(model_file))

        prep = ov.preprocess.PrePostProcessor(model)
        prep.input("image").tensor().set_layout(ov.Layout("NCHW"))
        prep.input("image").preprocess().scale([255.0, 255.0, 255.0])
        model = prep.build()

        if self.device == "NPU":
            static_shapes = {}
            for inp in model.inputs:
                name = inp.get_any_name()
                if name == "image":
                    static_shapes[name] = ov.PartialShape([1, 3, self.INPUT_SIZE, self.INPUT_SIZE])
                else:
                    static_shapes[name] = ov.PartialShape([1, 2])
            model.reshape(static_shapes)
            print(f"NPU: reshaped inputs to static {static_shapes}")

        self.compiled_model = self.core.compile_model(model, self.device)
        self.load_time = time.time() - load_start
        print(f"Model loaded in {self.load_time:.2f}s")

    def _resolve_model_file(self):
        if self.model_path.is_dir():
            preferred = self.model_path / "model.xml"
            if preferred.exists():
                return preferred
            xml_files = list(self.model_path.glob("*.xml"))
            if not xml_files:
                raise FileNotFoundError(f"No .xml model found in {self.model_path}")
            return xml_files[0]
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        return self.model_path

    def _preprocess(self, image_bgr):
        orig_h, orig_w = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.INPUT_SIZE, self.INPUT_SIZE), interpolation=cv2.INTER_CUBIC)
        blob = resized.astype(np.float32).transpose(2, 0, 1)[np.newaxis, ...]
        return blob, orig_h, orig_w

    def _build_inputs(self, blob, orig_h, orig_w):
        scale_factor = np.array(
            [[self.INPUT_SIZE / orig_h, self.INPUT_SIZE / orig_w]], dtype=np.float32
        )
        im_shape = np.array([[self.INPUT_SIZE, self.INPUT_SIZE]], dtype=np.float32)
        feed = {}
        for inp in self.compiled_model.inputs:
            name = inp.get_any_name()
            if name == "image":
                feed[name] = blob
            elif name == "scale_factor":
                feed[name] = scale_factor
            elif name == "im_shape":
                feed[name] = im_shape
        return feed

    def _postprocess(self, det, count, orig_h, orig_w):
        if det is None or det.size == 0 or det.ndim != 2 or det.shape[1] < 6:
            return []

        num = det.shape[0]
        if count is not None and count.size > 0:
            num = max(0, min(int(count.reshape(-1)[0]), num))
        det = det[:num]

        cls = det[:, 0].astype(int)
        score = det[:, 1]
        coords = det[:, 2:6]

        results = []
        for i in range(len(cls)):
            if score[i] <= self.threshold:
                continue
            cls_id = cls[i]
            if cls_id < 0 or cls_id >= len(self.LABEL_LIST):
                continue
            xmin, ymin, xmax, ymax = coords[i]
            xmin = float(max(0, min(xmin, orig_w)))
            ymin = float(max(0, min(ymin, orig_h)))
            xmax = float(max(0, min(xmax, orig_w)))
            ymax = float(max(0, min(ymax, orig_h)))
            if xmax <= xmin or ymax <= ymin:
                continue
            results.append({
                "cls_id": int(cls_id),
                "label": self.LABEL_LIST[cls_id],
                "score": float(score[i]),
                "coordinate": [xmin, ymin, xmax, ymax],
            })

        results.sort(key=lambda b: b["score"], reverse=True)
        return results

    def detect(self, image_input):
        if isinstance(image_input, (str, Path)):
            image = cv2.imread(str(image_input))
            if image is None:
                raise FileNotFoundError(f"Unable to read image: {image_input}")
        elif isinstance(image_input, Image.Image):
            image = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
        else:
            raise ValueError("image_input must be a file path or PIL Image")

        start = time.time()
        blob, orig_h, orig_w = self._preprocess(image)
        feed = self._build_inputs(blob, orig_h, orig_w)
        result = self.compiled_model(feed)

        outputs = {out.get_any_name(): np.array(result[out].data) for out in self.compiled_model.outputs}
        det = next((v for v in outputs.values() if v.ndim == 2 and v.shape[1] >= 6), None)
        count = next((v for v in outputs.values() if v.ndim == 1), None)

        boxes = self._postprocess(det, count, orig_h, orig_w)
        infer_time = time.time() - start
        self.inference_times.append(infer_time)

        return {"boxes": boxes, "inference_time": infer_time, "image_size": (orig_w, orig_h)}

    def visualize(self, image_path, boxes, output_path):
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Unable to read image: {image_path}")
        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)

        font_size = int(0.018 * img_pil.width) + 2
        font = ImageFont.load_default()
        for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, font_size)
                    break
                except Exception:
                    pass

        colors = [
            (128, 64, 128), (232, 35, 244), (70, 70, 70), (156, 102, 102),
            (0, 220, 220), (35, 142, 107), (152, 251, 152), (180, 130, 70),
            (0, 0, 255), (142, 0, 0), (230, 0, 0),
        ]
        thickness = max(2, int(max(img_pil.size) * 0.002))

        for box in boxes:
            xmin, ymin, xmax, ymax = box["coordinate"]
            color = colors[box["cls_id"] % len(colors)]
            draw.rectangle([xmin, ymin, xmax, ymax], outline=color, width=thickness)
            text = f"{box['label']} {box['score']:.2f}"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.rectangle([(xmin, ymin - th - 2), (xmin + tw + 4, ymin)], fill=color)
            draw.text((xmin + 2, ymin - th - 2), text, fill=(255, 255, 255), font=font)

        img_pil.save(output_path)


def main():
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    cfg = config.get("layout_detection", {})

    def resolve(p):
        p = Path(p)
        return p if p.is_absolute() else config_path.parent / p

    model_path = resolve(cfg.get("model_path", "../models/PP-DocLayoutV3-ov"))
    precision = cfg.get("precision")
    if precision:
        model_path = model_path / precision
    input_path = resolve(cfg.get("input_path", "./input"))
    output_path = resolve(cfg.get("output_dir", "./output"))
    device = cfg.get("device", "GPU")
    threshold = cfg.get("threshold", 0.5)
    do_visualize = cfg.get("visualize", False)

    print("=" * 80)
    print("PP-DocLayoutV3 Layout Detection")
    print("=" * 80)
    print(f"  Model: {model_path}")
    print(f"  Device: {device}")
    print(f"  Precision: {precision}")
    print(f"  Threshold: {threshold}")
    print(f"  Input: {input_path}")
    print(f"  Output: {output_path}")
    print()

    detector = LayoutDetectorV3(model_path=model_path, device=device, threshold=threshold)

    if not input_path.exists():
        print(f"Input path does not exist: {input_path}")
        return

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    if input_path.is_file():
        image_files = [input_path] if input_path.suffix.lower() in exts else []
    else:
        image_files = sorted({p for e in exts for p in input_path.glob(f"*{e}")})

    if not image_files:
        print("No image files found")
        return

    output_path.mkdir(parents=True, exist_ok=True)
    print(f"Processing {len(image_files)} image(s)...")
    print("=" * 80)

    total_boxes = 0
    for i, img_file in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] {img_file.name}")
        try:
            result = detector.detect(img_file)
            boxes = result["boxes"]
            total_boxes += len(boxes)
            print(f"  Inference time: {result['inference_time']:.3f}s")
            print(f"  Detected {len(boxes)} regions:")

            counts = {}
            for b in boxes:
                counts[b["label"]] = counts.get(b["label"], 0) + 1
            for label, c in sorted(counts.items()):
                print(f"    - {label}: {c}")

            json_file = output_path / f"{img_file.stem}_layout.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump({
                    "input_path": str(img_file.absolute()),
                    "image_size": result["image_size"],
                    "boxes": boxes,
                    "inference_time": result["inference_time"],
                }, f, indent=2, ensure_ascii=False)

            if do_visualize:
                detector.visualize(img_file, boxes, output_path / f"{img_file.stem}_layout.jpg")
        except Exception as e:
            print(f"  Error: {e}")

    print("\n" + "=" * 80)
    print(f"Processed {len(image_files)} image(s), {total_boxes} regions total")
    if detector.inference_times:
        avg = sum(detector.inference_times) / len(detector.inference_times)
        print(f"Avg inference time: {avg:.3f}s")
    print(f"Results saved to: {output_path.absolute()}")


if __name__ == "__main__":
    main()
