"""Detection Service Client - Interface to call PP-DocLayoutV2 detection service"""
import requests
import base64
import io
import numpy as np
from pathlib import Path
from typing import Union, List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont


class DetectionServiceError(Exception):
    pass


def detect_layout(
    image: Union[str, Path, Image.Image],
    service_url: str = "http://127.0.0.1:9902",
    timeout: int = 60,
    use_base64: bool = False
) -> Dict[str, Any]:
    """Detect layout regions in an image using PP-DocLayoutV2 service"""
    if isinstance(image, (str, Path)):
        image_path = Path(image)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        pil_image = Image.open(image_path).convert('RGB')
    elif isinstance(image, Image.Image):
        pil_image = image
    elif isinstance(image, np.ndarray):
        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(image).convert('RGB')
    else:
        raise TypeError(f"Unsupported image type: {type(image)}")

    try:
        if use_base64:
            result = _detect_base64(pil_image, service_url, timeout)
        else:
            result = _detect_file(pil_image, service_url, timeout)

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            raise DetectionServiceError(f"Detection failed: {error_msg}")

        return {
            'boxes': result.get('boxes', []),
            'inference_time': result.get('inference_time', 0),
            'image_size': result.get('image_size', [0, 0]),
            'num_regions': result.get('num_regions', 0)
        }

    except requests.exceptions.ConnectionError:
        raise DetectionServiceError(
            f"Cannot connect to detection service at {service_url}. "
            f"Start service with: python ocr_services/layout_detection_server.py"
        )
    except requests.exceptions.Timeout:
        raise DetectionServiceError(
            f"Detection service timeout after {timeout}s"
        )
    except Exception as e:
        if isinstance(e, DetectionServiceError):
            raise
        raise DetectionServiceError(f"Detection failed: {e}")


def _detect_file(
    pil_image: Image.Image,
    service_url: str,
    timeout: int
) -> Dict[str, Any]:
    """Detect using file upload"""
    img_buffer = io.BytesIO()
    pil_image.save(img_buffer, format='JPEG', quality=95)
    img_buffer.seek(0)

    files = {'file': ('image.jpg', img_buffer, 'image/jpeg')}
    response = requests.post(
        f"{service_url}/detect/file",
        files=files,
        timeout=timeout,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()


def _detect_base64(
    pil_image: Image.Image,
    service_url: str,
    timeout: int
) -> Dict[str, Any]:
    """Detect using base64 encoding"""
    img_buffer = io.BytesIO()
    pil_image.save(img_buffer, format='JPEG', quality=95)
    img_buffer.seek(0)
    image_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')

    payload = {'image_base64': image_base64}
    response = requests.post(
        f"{service_url}/detect/base64",
        json=payload,
        timeout=timeout,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()


def check_service_health(service_url: str = "http://127.0.0.1:9902") -> bool:
    """Check if detection service is healthy"""
    try:
        response = requests.get(f"{service_url}/health", timeout=5, proxies={"http": None, "https": None})
        if response.status_code == 200:
            data = response.json()
            return data.get('status') == 'healthy'
        return False
    except Exception:
        return False


def filter_boxes_by_label(
    boxes: List[Dict[str, Any]],
    labels: Union[str, List[str]],
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """Filter detection boxes by label and score"""
    if isinstance(labels, str):
        labels = [labels]

    filtered = []
    for box in boxes:
        if box['label'] in labels and box['score'] >= min_score:
            filtered.append(box)

    return filtered


def sort_boxes_by_position(
    boxes: List[Dict[str, Any]],
    direction: str = 'vertical'
) -> List[Dict[str, Any]]:
    """Sort boxes by position (top-to-bottom or left-to-right)"""
    if direction == 'vertical':
        return sorted(boxes, key=lambda b: (b['coordinate'][1], b['coordinate'][0]))
    elif direction == 'horizontal':
        return sorted(boxes, key=lambda b: (b['coordinate'][0], b['coordinate'][1]))
    else:
        raise ValueError(f"Invalid direction: {direction}. Use 'vertical' or 'horizontal'")


def expand_box(
    box: Dict[str, Any],
    margin: Union[int, tuple] = 10,
    image_size: Optional[tuple] = None
) -> Dict[str, Any]:
    """Expand a bounding box by margin"""
    x1, y1, x2, y2 = box['coordinate']

    if isinstance(margin, int):
        margin_h = margin_v = margin
    else:
        margin_h, margin_v = margin

    new_x1 = x1 - margin_h
    new_y1 = y1 - margin_v
    new_x2 = x2 + margin_h
    new_y2 = y2 + margin_v

    if image_size:
        w, h = image_size
        new_x1 = max(0, new_x1)
        new_y1 = max(0, new_y1)
        new_x2 = min(w, new_x2)
        new_y2 = min(h, new_y2)

    expanded_box = box.copy()
    expanded_box['coordinate'] = [new_x1, new_y1, new_x2, new_y2]
    return expanded_box


def merge_overlapping_boxes(
    boxes: List[Dict[str, Any]],
    iou_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """Merge overlapping boxes with high IoU"""
    if not boxes:
        return []

    def compute_iou(box1, box2):
        """Compute IoU between two boxes"""
        x1_1, y1_1, x2_1, y2_1 = box1['coordinate']
        x1_2, y1_2, x2_2, y2_2 = box2['coordinate']

        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)

        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0

    def merge_two_boxes(box1, box2):
        """Merge two boxes by taking the union"""
        x1_1, y1_1, x2_1, y2_1 = box1['coordinate']
        x1_2, y1_2, x2_2, y2_2 = box2['coordinate']

        merged = box1.copy()
        merged['coordinate'] = [
            min(x1_1, x1_2),
            min(y1_1, y1_2),
            max(x2_1, x2_2),
            max(y2_1, y2_2)
        ]
        merged['score'] = max(box1['score'], box2['score'])
        return merged

    merged = []
    used = set()

    for i, box1 in enumerate(boxes):
        if i in used:
            continue

        current = box1
        merged_with = []

        for j, box2 in enumerate(boxes[i+1:], start=i+1):
            if j in used:
                continue

            if box1['label'] == box2['label']:
                iou = compute_iou(current, box2)
                if iou >= iou_threshold:
                    current = merge_two_boxes(current, box2)
                    merged_with.append(j)

        merged.append(current)
        used.add(i)
        used.update(merged_with)

    return merged


def detect_page_layout(
    page_image: Image.Image,
    service_url: str,
    target_labels: Optional[List[str]] = None,
    min_score: float = 0.5,
    sort: bool = True,
    expand_margin: int = 0
) -> List[Dict[str, Any]]:
    """Detect layout and return filtered, sorted boxes"""
    result = detect_layout(page_image, service_url)
    boxes = result['boxes']
    image_size = tuple(result['image_size'])

    if target_labels:
        boxes = filter_boxes_by_label(boxes, target_labels, min_score)
    else:
        boxes = [b for b in boxes if b['score'] >= min_score]

    if sort:
        boxes = sort_boxes_by_position(boxes, 'vertical')

    if expand_margin > 0:
        boxes = [expand_box(b, expand_margin, image_size) for b in boxes]

    return boxes


def draw_detection_boxes(
    image: Union[Image.Image, np.ndarray],
    boxes: List[Dict[str, Any]],
    output_path: Union[str, Path],
    font_size: int = None,
    line_width: int = None
) -> None:
    """Draw detection boxes on image and save"""
    if isinstance(image, np.ndarray):
        pil_image = Image.fromarray(image).convert('RGB')
    else:
        pil_image = image.convert('RGB')

    draw = ImageDraw.Draw(pil_image)

    if font_size is None:
        font_size = max(12, int(pil_image.width * 0.015))
    if line_width is None:
        line_width = max(2, int(pil_image.width * 0.002))

    try:
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font = None
        for fp in font_paths:
            if Path(fp).exists():
                try:
                    font = ImageFont.truetype(fp, font_size)
                    break
                except:
                    continue
        if font is None:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    colors = {
        'text': (0, 128, 255),
        'table': (255, 128, 0),
        'image': (128, 255, 0),
        'display_formula': (255, 0, 128),
        'title': (255, 255, 0),
        'chart': (128, 0, 255),
    }
    default_color = (255, 0, 0)

    for box in boxes:
        label = box['label']
        score = box['score']
        x1, y1, x2, y2 = box['coordinate']

        color = colors.get(label, default_color)

        draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)

        text = f"{label} {score:.2f}"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1] + 4
        except:
            text_width, text_height = draw.textsize(text, font=font)
            text_height += 4

        label_x = x1
        label_y = y1 - text_height if y1 > text_height else y1

        draw.rectangle(
            [label_x, label_y, label_x + text_width + 4, label_y + text_height],
            fill=color
        )
        draw.text((label_x + 2, label_y), text, fill=(255, 255, 255), font=font)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil_image.save(output_path, quality=95)

