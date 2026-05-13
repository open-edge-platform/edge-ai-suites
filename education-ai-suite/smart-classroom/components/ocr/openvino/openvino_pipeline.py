import numpy as np
import cv2
import math
from typing import List, Tuple, Optional

def preprocess_det(img: np.ndarray, size: int = 640) -> np.ndarray:

    resized = cv2.resize(img, (size, size))
    
    img_norm = np.transpose(resized, [2, 0, 1]) / 255.0
    img_norm = np.expand_dims(img_norm, 0)
    
    img_mean = np.array([0.485, 0.456, 0.406]).reshape((3, 1, 1))
    img_std = np.array([0.229, 0.224, 0.225]).reshape((3, 1, 1))
    img_norm -= img_mean
    img_norm /= img_std
    
    return img_norm.astype(np.float32)

def preprocess_rec(img: np.ndarray, 
                   rec_image_height: int = 48, 
                   rec_image_width: int = 320,
                   max_wh_ratio: float = None) -> np.ndarray:

    imgC, imgH, imgW = 3, rec_image_height, rec_image_width
    
    if max_wh_ratio is not None:
        imgW = int(imgH * max_wh_ratio)
        imgW = max(imgW, rec_image_width) 
    
    h, w = img.shape[:2]
    ratio = w / float(h)
    
    if math.ceil(imgH * ratio) > imgW:
        resized_w = imgW
    else:
        resized_w = int(math.ceil(imgH * ratio))
    
    resized_image = cv2.resize(img, (resized_w, imgH))
    resized_image = resized_image.astype('float32')
    
    resized_image = resized_image.transpose((2, 0, 1)) / 255
    resized_image -= 0.5
    resized_image /= 0.5
    
    padding_im = np.zeros((imgC, imgH, imgW), dtype=np.float32)
    padding_im[:, :, 0:resized_w] = resized_image
    
    return padding_im


def boxes_from_bitmap(pred: np.ndarray, 
                      bitmap: np.ndarray, 
                      dest_width: int, 
                      dest_height: int,
                      box_thresh: float = 0.45,
                      unclip_ratio: float = 1.6,
                      max_candidates: int = 1000) -> Tuple[List, List]:
    import pyclipper
    from shapely.geometry import Polygon
    
    height, width = bitmap.shape
    boxes = []
    scores = []
    
    contours, _ = cv2.findContours(
        (bitmap * 255).astype(np.uint8), 
        cv2.RETR_LIST, 
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    for contour in contours[:max_candidates]:
        epsilon = 0.002 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        points = approx.reshape((-1, 2))
        
        if len(points) < 4:
            continue
        
        score = box_score_fast(pred, contour.squeeze())
        if score < box_thresh:
            continue
        
        if len(points) > 4:
            rect = cv2.minAreaRect(points)
            points = cv2.boxPoints(rect)
        
        poly = Polygon(points)
        if not poly.is_valid or poly.area < 1:
            continue
            
        distance = poly.area * unclip_ratio / poly.length
        offset = pyclipper.PyclipperOffset()
        offset.AddPath(points.tolist(), pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        expanded = offset.Execute(distance)
        
        if len(expanded) == 0:
            continue
        
        expanded_points = np.array(expanded[0])
        rect = cv2.minAreaRect(expanded_points)
        box = cv2.boxPoints(rect)
        box = np.intp(box)
        
        box[:, 0] = np.clip(box[:, 0] / width * dest_width, 0, dest_width)
        box[:, 1] = np.clip(box[:, 1] / height * dest_height, 0, dest_height)
        
        boxes.append(box)
        scores.append(score)
    
    return boxes, scores


def box_score_fast(bitmap: np.ndarray, points: np.ndarray) -> float:

    h, w = bitmap.shape[:2]
    box = points.copy()
    xmin = np.clip(np.floor(box[:, 0].min()).astype(np.int32), 0, w - 1)
    xmax = np.clip(np.ceil(box[:, 0].max()).astype(np.int32), 0, w - 1)
    ymin = np.clip(np.floor(box[:, 1].min()).astype(np.int32), 0, h - 1)
    ymax = np.clip(np.ceil(box[:, 1].max()).astype(np.int32), 0, h - 1)
    
    mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    box[:, 0] = box[:, 0] - xmin
    box[:, 1] = box[:, 1] - ymin
    cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
    
    return cv2.mean(bitmap[ymin:ymax + 1, xmin:xmax + 1], mask)[0]


def sorted_boxes(boxes: List[np.ndarray]) -> List[np.ndarray]:
    def box_sort_key(box):
        return (box[:, 1].min(), box[:, 0].min())
    return sorted(boxes, key=box_sort_key)


def filter_boxes(boxes: List[np.ndarray], 
                 shape: Tuple[int, int],
                 min_size: int = 3) -> List[np.ndarray]:
    height, width = shape[:2]
    filtered = []
    for box in boxes:
        box = order_points(box)
        box = np.clip(box, 0, [width - 1, height - 1])
        rect_width = int(np.linalg.norm(box[0] - box[1]))
        rect_height = int(np.linalg.norm(box[0] - box[3]))
        if rect_width > min_size and rect_height > min_size:
            filtered.append(box)
    return filtered


def order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def get_rotate_crop_image(img: np.ndarray, box: np.ndarray) -> Optional[np.ndarray]:
    box = np.array(box).astype(np.float32)
    img_crop_width = int(max(
        np.linalg.norm(box[0] - box[1]),
        np.linalg.norm(box[2] - box[3])
    ))
    img_crop_height = int(max(
        np.linalg.norm(box[0] - box[3]),
        np.linalg.norm(box[1] - box[2])
    ))
    
    if img_crop_width < 5 or img_crop_height < 5:
        return None
    
    pts_std = np.array([
        [0, 0],
        [img_crop_width, 0],
        [img_crop_width, img_crop_height],
        [0, img_crop_height]
    ], dtype=np.float32)
    
    M = cv2.getPerspectiveTransform(box, pts_std)
    dst_img = cv2.warpPerspective(
        img, M, (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC
    )
    
    dst_img_height, dst_img_width = dst_img.shape[:2]
    if dst_img_height * 1.0 / dst_img_width >= 1.5:
        dst_img = np.rot90(dst_img)
    
    return dst_img


def ctc_decode(output: np.ndarray, char_dict: List[str]) -> Tuple[str, float]:
    pred = output[0]
    pred_idx = np.argmax(pred, axis=1)
    pred_prob = np.max(pred, axis=1)
    
    text = []
    conf_list = []
    prev_idx = 0 
    
    for i, idx in enumerate(pred_idx):
        if idx != 0 and idx != prev_idx:
            if idx < len(char_dict):
                text.append(char_dict[idx])
                conf_list.append(pred_prob[i])
        prev_idx = idx
    
    result_text = ''.join(text)
    avg_conf = float(np.mean(conf_list)) if conf_list else 0.0
    
    return result_text, avg_conf


def ctc_decode_batch(outputs: np.ndarray, char_dict: List[str]) -> List[Tuple[str, float]]:
    results = []
    for output in outputs:
        pred_idx = np.argmax(output, axis=1)
        pred_prob = np.max(output, axis=1)
        
        text = []
        conf_list = []
        prev_idx = 0
        
        for i, idx in enumerate(pred_idx):
            if idx != 0 and idx != prev_idx:
                if idx < len(char_dict):
                    text.append(char_dict[idx])
                    conf_list.append(pred_prob[i])
            prev_idx = idx
        
        result_text = ''.join(text)
        avg_conf = float(np.mean(conf_list)) if conf_list else 0.0
        results.append((result_text, avg_conf))
    
    return results

def prep_for_recognition(boxes: List[np.ndarray], 
                         img: np.ndarray) -> Tuple[List[np.ndarray], List[int]]:
    img_crop_list = []
    valid_indices = []
    
    for i, box in enumerate(boxes):
        crop = get_rotate_crop_image(img, box)
        if crop is not None:
            img_crop_list.append(crop)
            valid_indices.append(i)
    
    return img_crop_list, valid_indices


def batch_text_boxes(img_crop_list: List[np.ndarray],
                     indices: np.ndarray,
                     beg_img_no: int,
                     batch_num: int,
                     rec_image_height: int = 48,
                     rec_image_width: int = 320) -> np.ndarray:

    img_num = len(img_crop_list)
    end_img_no = min(img_num, beg_img_no + batch_num)
    
    max_wh_ratio = 0
    for ino in range(beg_img_no, end_img_no):
        h, w = img_crop_list[indices[ino]].shape[:2]
        wh_ratio = w * 1.0 / h
        max_wh_ratio = max(max_wh_ratio, wh_ratio)
    
    norm_img_batch = []
    for ino in range(beg_img_no, end_img_no):
        norm_img = preprocess_rec(
            img_crop_list[indices[ino]], 
            rec_image_height, 
            rec_image_width,
            max_wh_ratio
        )
        norm_img_batch.append(norm_img[np.newaxis, :])
    
    return np.concatenate(norm_img_batch)
