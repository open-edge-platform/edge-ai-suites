import os
import numpy as np
import argparse

SIZE = (640, 480)
CLASS_TO_ID = {"car": 0, "truck": 1, "bus": 2, "motorcycle": 3, "bicycle": 4, "person": 5}

parser = argparse.ArgumentParser(description="Evaluate model using ground-truth and prediction files.")
parser.add_argument("--gt_dir", type=str, required=True, help="input gt file folder.")
parser.add_argument("--pred_dir", type=str, required=True, help="input predication file folder.")
parser.add_argument("--thres", type=float, default=0.5, help="iou threshold.")


def compute_ap(rec, prec, use_07_metric=False):
    """Compute AP given precision and recall. If use_07_metric is true, uses
    the VOC 07 11-point method (default:False).
    """
    if use_07_metric:
        # 11 point metric
        ap = 0.
        for t in np.arange(0., 1.1, 0.1):
            if np.sum(rec >= t) == 0:
                p = 0
            else:
                p = np.max(prec[rec >= t])
            ap = ap + p / 11.
    else:
        # correct AP calculation
        # first append sentinel values at the end
        mrec = np.concatenate(([0.], rec, [1.]))
        mpre = np.concatenate(([0.], prec, [0.]))

        # compute the precision envelope
        for i in range(mpre.size - 1, 0, -1):
            mpre[i - 1] = np.maximum(mpre[i - 1], mpre[i])

        # to calculate area under PR curve, look for points
        # where X axis (recall) changes value
        i = np.where(mrec[1:] != mrec[:-1])[0]

        # and sum (\Delta recall) * prec
        ap = np.sum((mrec[i + 1] - mrec[i]) * mpre[i + 1])
    return ap

def cxcywhn2xyxy(cxcywhn: list, size: list):
    img_width, img_height = size
    cx, cy, w, h = cxcywhn
    xmin = (cx - w / 2) * img_width
    ymin = (cy - h / 2) * img_height
    xmax = (cx + w / 2) * img_width
    ymax = (cy + h / 2) * img_height
    return [xmin, ymin, xmax, ymax]

def xywh2xyxy(box: list):
    x, y, w, h = box
    xmin = x
    ymin = y
    xmax = x + w
    ymax = y + h
    return [xmin, ymin, xmax, ymax]

def load_ground_truth(gt_dir, target_class_id):
    gt_data = {}
    image_id = 0
    npos = 0
    filenames = sorted(os.listdir(gt_dir))
    for filename in filenames:
        if filename.endswith(".txt"):
            with open(os.path.join(gt_dir, filename), "r") as f:
                boxes = []
                lines = f.readlines()
                for line in lines:
                    parts = list(map(float, line.strip().split()))
                    class_id = int(parts[0])
                    if class_id == target_class_id:
                        xmin, ymin, xmax, ymax = cxcywhn2xyxy(parts[1:], SIZE)
                        boxes.append([xmin, ymin, xmax, ymax])
                det = [False] * len(boxes)
                npos += len(boxes)
                gt_data[image_id] = {'bbox': np.array(boxes), 'det': det}
            image_id += 1
    return gt_data, npos


def load_pred_data(pred_dir, target_class_id):
    pred_data = {}
    image_id = 0
    image_ids = []
    confidence = []
    boxes = []
    
    filenames = sorted(os.listdir(pred_dir))
    for filename in filenames:
        if filename.endswith(".txt"):
            with open(os.path.join(pred_dir, filename), "r") as f:
                lines = f.readlines()
                for line in lines:
                    parts = list(map(float, line.strip().split()))
                    class_id = int(parts[0])
                    if class_id == target_class_id:
                        conf = float(parts[1])
                        xmin, ymin, xmax, ymax = xywh2xyxy(parts[2:])
                        boxes.append([xmin, ymin, xmax, ymax])
                        image_ids.append(image_id)
                        confidence.append(conf)
            image_id += 1
    return image_ids, np.array(confidence), np.array(boxes)

def calculate_bbox_iou(box1, box2):
    xmin1, ymin1, xmax1, ymax1 = box1
    xmin2, ymin2, xmax2, ymax2 = box2
    
    xi1 = max(xmin1, xmin2)
    yi1 = max(ymin1, ymin2)
    xi2 = min(xmax1, xmax2)
    yi2 = min(ymax1, ymax2)

    inter_width = max(0, xi2 - xi1 + 1)
    inter_height = max(0, yi2 - yi1 + 1)
    inter_area = inter_width * inter_height
    
    box1_area = (xmax1 - xmin1) * (ymax1 - ymin1)
    box2_area = (xmax2 - xmin2) * (ymax2 - ymin2)
    
    union_area = box1_area + box2_area - inter_area
    
    iou = inter_area / union_area if union_area != 0 else 0
    
    return iou

def eval(gt_dir, pred_dir, classname, ovthresh=0.5, use_07_metric=False):
    target_class_id = CLASS_TO_ID[classname]
    class_recs, npos = load_ground_truth(gt_dir, target_class_id)
    # print(class_recs, npos)
    image_ids, confidence, BB = load_pred_data(pred_dir, target_class_id)

    # sort by confidence
    sorted_ind = np.argsort(-confidence)
    BB = BB[sorted_ind, :]
    image_ids = [image_ids[x] for x in sorted_ind]

    # go down dets and mark TPs and FPs
    nd = len(image_ids)
    tp = np.zeros(nd)
    fp = np.zeros(nd)
    for d in range(nd):
        R = class_recs[image_ids[d]]
        bb = BB[d, :].astype(float)
        ovmax = -np.inf
        BBGT = R['bbox'].astype(float)

        if BBGT.size > 0:
            # compute overlaps
            # intersection
            # print(BBGT, BBGT.size)
            ixmin = np.maximum(BBGT[:, 0], bb[0])
            iymin = np.maximum(BBGT[:, 1], bb[1])
            ixmax = np.minimum(BBGT[:, 2], bb[2])
            iymax = np.minimum(BBGT[:, 3], bb[3])
            iw = np.maximum(ixmax - ixmin + 1., 0.)
            ih = np.maximum(iymax - iymin + 1., 0.)
            inters = iw * ih

            # union
            uni = ((bb[2] - bb[0] + 1.) * (bb[3] - bb[1] + 1.) +
                   (BBGT[:, 2] - BBGT[:, 0] + 1.) *
                   (BBGT[:, 3] - BBGT[:, 1] + 1.) - inters)
            overlaps = inters / uni
            ovmax = np.max(overlaps)
            jmax = np.argmax(overlaps)

        if ovmax > ovthresh:
            if not R['det'][jmax]:
                tp[d] = 1.
                R['det'][jmax] = 1
            else:
                fp[d] = 1.
        else:
            fp[d] = 1.

    # compute precision recall
    fp = np.cumsum(fp)
    tp = np.cumsum(tp)
    rec = tp / float(npos)
    # avoid divide by zero in case the first detection matches a difficult
    # ground truth
    prec = tp / np.maximum(tp + fp, np.finfo(np.float64).eps)
    ap = compute_ap(rec, prec, use_07_metric)

    return rec, prec, ap


def evaluate_model(gt_dir, pred_dir, ovthresh=0.5, use_07_metric=False):
    rec1, prec1, ap1 = eval(gt_dir, pred_dir, "car", ovthresh, use_07_metric)
    rec2, prec2, ap2 = eval(gt_dir, pred_dir, "truck", ovthresh, use_07_metric)
    print("****************************************")
    print("category:    car     truck")
    print(f"ap:        {ap1:.4f}    {ap2:.4f}")
    print("****************************************")
    print(f"mAP: {(ap1 + ap2) / 2:.4f}", )


if __name__ == "__main__":
    args = parser.parse_args()
    gt_dir = args.gt_dir
    pred_dir = args.pred_dir
    thres = args.thres

    evaluate_model(gt_dir, pred_dir, thres, False)
