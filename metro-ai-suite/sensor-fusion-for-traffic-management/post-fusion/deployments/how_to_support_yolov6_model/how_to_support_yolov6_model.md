

# How to support YOLOv6 model in TFCC pipeline

This document shows how to support the YOLOv6s model in the TFCC pipeline, including model retraining, quantization, and other operations.

## Python environment set-up

```bash

# Step 1: Create virtual environment
python3 -m venv yolov6_env

# Step 2: Activate virtual environment
source yolov6_env/bin/activate

# Step 3: Upgrade pip to latest version
python3 -m pip install --upgrade pip

# Step4: Install related libs
pip3 install -r requirements.txt
```



## Download YOLOv6 source code and models

```bash
git clone https://github.com/meituan/YOLOv6.git YOLOv6
cd YOLOv6
mkdir weights
cd weights
curl -k -o yolov6s.pt https://github.com/meituan/YOLOv6/releases/download/0.4.0/yolov6s.pt  -L
cd ..
```

**In the following, `YOLOv6_DIR` will be used to represent the path to the YOLOv6 source code you downloaded above.**



### Issue fix

Newer versions of pytorch will report the following error when loading the yolov6 model:

> _pickle.UnpicklingError: Weights only load failed. This file can still be loaded, to do so you have two options, do those steps only if you trust the source of the checkpoint. 
>         (1) In PyTorch 2.6, we changed the default value of the `weights_only` argument in `torch.load` from `False` to `True`. Re-running `torch.load` with `weights_only` set to `False` will likely succeed, but it can result in arbitrary code execution. Do it only if you got the file from a trusted source.
>         (2) Alternatively, to load with `weights_only=True` please check the recommended steps in the following error message.
>         WeightsUnpickler error: Unsupported global: GLOBAL yolov6.models.yolo.Model was not an allowed global by default. Please use `torch.serialization.add_safe_globals([Model])` or the `torch.serialization.safe_globals([Model])` context manager to allowlist this global if you trust this class/function.
>
> Check the documentation of torch.load to learn more about types accepted by default with weights_only https://pytorch.org/docs/stable/generated/torch.load.html.



Change `torch.load(weights, map_location=map_location)` in the `yolov6/utils/checkpoint.py` file to `torch.load(weights, map_location=map_location, weights_only=False)`

Change `torch.load(ckpt_path, map_location=torch.device("cpu"))` in the `yolov6/utils/checkpoint.py` file to `torch.load(ckpt_path, map_location=torch.device("cpu"), weights_only=False)`





## Model retraining(Optional)

If you want to retrain your own model based on official model weights, you can refer to the following steps.

You can get original COCO dataset from the official website [COCO](https://cocodataset.org/#download). **Make sure your dataset structure as follows:**

```
├── coco
│   ├── annotations
│   │   ├── instances_train2017.json
│   │   └── instances_val2017.json
│   ├── images
│   │   ├── train2017
│   │   └── val2017
│   ├── labels
│   │   ├── train2017
│   │   ├── val2017
│   ├── LICENSE
│   ├── README.txt
```



### Create customized dataset

Suppose you only want to detect the following categories: `bicycle, car, motorcycle, bus, truck`.

Now you need to create your own customized dataset.

Run the following command to filter COCO YOLO dataset for specific vehicle classes (`bicycle, car, motorcycle, bus, truck`).

```bash
python3 filter_coco_vehicle.py --input_root /path/to/coco --output_root /path/to/output --splits train2017 val2017
```

After running the command you will get your customized dataset and your dataset structure are as follows:

```
├── coco_vehicle
│   ├── images
│   │   ├── train2017
│   │   └── val2017
│   ├── labels
│   │   ├── train2017
│   │   ├── val2017
```

The  `filter_coco_vehicle.py` script is as follows:

```python
import os
import shutil
from tqdm import tqdm
import argparse

# Default COCO class mapping (original YOLO class ID → new ID)
DEFAULT_CLASS_MAPPING = {1: 0, 2: 1, 3: 2, 5: 3, 7: 4}  # bicycle, car, motorcycle, bus, truck


def process_split(split, input_root, output_root, class_mapping):
    """
    Process a single dataset split (e.g., train2017 or val2017).
    Copies images and filtered label files containing only target classes.
    """
    img_src_dir = os.path.join(input_root, "images", split)
    label_src_dir = os.path.join(input_root, "labels", split)
    img_dst_dir = os.path.join(output_root, "images", split)
    label_dst_dir = os.path.join(output_root, "labels", split)

    os.makedirs(img_dst_dir, exist_ok=True)
    os.makedirs(label_dst_dir, exist_ok=True)

    target_ids = set(class_mapping.keys())

    if not os.path.exists(label_src_dir):
        print(f"Warning: Label directory {label_src_dir} does not exist. Skipping split {split}.")
        return

    label_files = [f for f in os.listdir(label_src_dir) if f.endswith(".txt")]

    for label_file in tqdm(label_files, desc=f"Processing {split}"):
        label_path = os.path.join(label_src_dir, label_file)
        img_file = label_file.replace(".txt", ".jpg")
        img_path = os.path.join(img_src_dir, img_file)

        valid_lines = []
        try:
            with open(label_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) != 5:
                        continue  # Skip invalid lines

                    try:
                        cls_id = int(parts[0])
                    except ValueError:
                        continue  # Skip lines with invalid class id

                    if cls_id in target_ids:
                        new_cls = class_mapping[cls_id]
                        new_line = f"{new_cls} {' '.join(parts[1:])}\n"
                        valid_lines.append(new_line)
        except Exception as e:
            print(f"Error reading label file {label_path}: {e}")
            continue

        # Copy image and write new label file if valid labels exist
        if valid_lines:
            if os.path.exists(img_path):
                try:
                    shutil.copy(img_path, os.path.join(img_dst_dir, img_file))
                except Exception as e:
                    print(f"Error copying image {img_path}: {e}")
            else:
                print(f"Warning: Missing image {img_path}")

            try:
                with open(os.path.join(label_dst_dir, label_file), "w") as f:
                    f.writelines(valid_lines)
            except Exception as e:
                print(f"Error writing label file {label_file}: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Filter COCO YOLO dataset for specific vehicle classes.")
    parser.add_argument(
        "--input_root",
        type=str,
        required=True,
        help="Root directory of the original dataset.",
    )
    parser.add_argument(
        "--output_root",
        type=str,
        required=True,
        help="Root directory for the filtered output dataset.",
    )
    parser.add_argument(
        "--splits",
        type=str,
        nargs="+",
        default=["train2017", "val2017"],
        help="Dataset splits to process (e.g., train2017 val2017).",
    )
    # Optionally allow custom class mapping via JSON string or file if needed
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Input root: {args.input_root}")
    print(f"Output root: {args.output_root}")
    print(f"Processing splits: {args.splits}")
    print(f"Using class mapping: {DEFAULT_CLASS_MAPPING}")

    for split in args.splits:
        process_split(split, args.input_root, args.output_root, DEFAULT_CLASS_MAPPING)

    print(f"\nDataset conversion completed! Output structure:\n{args.output_root}")
    print(
        """/
            ├── images/
            │   ├── train2017/     # Images containing only target classes
            │   └── val2017/
            └── labels/
                ├── train2017/     # YOLO labels for target classes only
                └── val2017/"""
    )


if __name__ == "__main__":
    main()

```



### Retrain model

Prepare your own customized dataset yaml file `$YOLOv6_DIR/data/coco_vehicle.yaml` based on `$YOLOv6_DIR/data/dataset.yaml`

```yaml
train: /path/to/coco_vehicle/images/train2017 # train images
val: /path/to/coco_vehicle/images/val2017 # val images

# whether it is coco dataset, only coco dataset should be set to True.
is_coco: False
# Classes
nc: 5  # number of classes
names: ["bicycle","car", "motorcycle", "bus","truck"]  # class names
```



You can refer to the `Finetune on custom data` section under [Quick Start](https://github.com/meituan/YOLOv6?tab=readme-ov-file#quick-start) in the official documentation to finetune the YOLOv6 model on your own customized dataset.

For example:

```bash
python3 tools/train.py --batch 32 --conf configs/yolov6s_finetune.py --img-size 640 --data data/coco_vehicle.yaml --fuse_ab --device 0 --epochs 100
```



Note if the downloaded model weights are placed in other directories, please modify `pretrained="weights/yolov6s.pt"` in `yolov6s_finetune.py`.



## Export Model to IR format

```bash
cd $YOLOv6_DIR

# use official model weights
python3 deploy/ONNX/export_onnx.py --weights ./weights/yolov6s.pt --img-size 640 640 --device cpu --simplify --ort
ovc ./weights/yolov6s.onnx --output_model ./weights/FP32/ --compress_to_fp16=False

# use retrained model weights
python3 deploy/ONNX/export_onnx.py --weights ./runs/train/exp/weights/best_ckpt.pt --img-size 640 640 --device cpu --simplify --ort
ovc ./runs/train/exp/weights/best_ckpt.onnx --output_model ./weights/FP32/ --compress_to_fp16=False
```

After this step you will get the yolov6s model file converted into the model format supported by OpenVINO.



## Model quantization

### For customized dataset

Run the following command to do model quantization.

```bash
cd $YOLOv6_DIR

python3 yolov6_quantization_with_accuracy_control.py --ov_model_path ./weights/FP32/yolov6s.xml --data data/coco_vehicle.yaml --weights ./runs/train/exp/weights/best_ckpt.pt --batch 1 --task val --device cpu --img-size 640 --height 640 --width 640 --specific-shape --verbose
```



After running the command, The quantized model will be located at `./weights/FP32/yolov6s_quantized.xml`.



The  `yolov6_quantization_with_accuracy_control.py` script is as follows:

```python
#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import argparse
import os
import os.path as osp
import sys

import openvino as ov
import nncf
from functools import partial

import torch
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from yolov6.core.evaler import Evaler
from yolov6.utils.general import increment_name, check_img_size
from yolov6.utils.config import Config
from yolov6.utils.torch_utils import time_sync, get_model_info
from yolov6.utils.nms import non_max_suppression
from yolov6.utils.events import NCOLS

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple
from loguru import logger

from tqdm import tqdm
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
import json
import io
import tempfile
import contextlib
from tabulate import tabulate
import itertools

COCO_CLASSES = ["bicycle", "car", "motorcycle", "bus", "truck"]

# COCO_CLASSES = [
#     "person",
#     "bicycle",
#     "car",
#     "motorcycle",
#     "airplane",
#     "bus",
#     "train",
#     "truck",
#     "boat",
#     "traffic light",
#     "fire hydrant",
#     "stop sign",
#     "parking meter",
#     "bench",
#     "bird",
#     "cat",
#     "dog",
#     "horse",
#     "sheep",
#     "cow",
#     "elephant",
#     "bear",
#     "zebra",
#     "giraffe",
#     "backpack",
#     "umbrella",
#     "handbag",
#     "tie",
#     "suitcase",
#     "frisbee",
#     "skis",
#     "snowboard",
#     "sports ball",
#     "kite",
#     "baseball bat",
#     "baseball glove",
#     "skateboard",
#     "surfboard",
#     "tennis racket",
#     "bottle",
#     "wine glass",
#     "cup",
#     "fork",
#     "knife",
#     "spoon",
#     "bowl",
#     "banana",
#     "apple",
#     "sandwich",
#     "orange",
#     "broccoli",
#     "carrot",
#     "hot dog",
#     "pizza",
#     "donut",
#     "cake",
#     "chair",
#     "couch",
#     "potted plant",
#     "bed",
#     "dining table",
#     "toilet",
#     "tv",
#     "laptop",
#     "mouse",
#     "remote",
#     "keyboard",
#     "cell phone",
#     "microwave",
#     "oven",
#     "toaster",
#     "sink",
#     "refrigerator",
#     "book",
#     "clock",
#     "vase",
#     "scissors",
#     "teddy bear",
#     "hair drier",
#     "toothbrush",
# ]


def per_class_AR_table(coco_eval, class_names=COCO_CLASSES, headers=["class", "AR"], colums=6):
    per_class_AR = {}
    recalls = coco_eval.eval["recall"]
    # dimension of recalls: [TxKxAxM]
    # recall has dims (iou, cls, area range, max dets)
    assert len(class_names) == recalls.shape[1]

    for idx, name in enumerate(class_names):
        recall = recalls[:, idx, 0, -1]
        recall = recall[recall > -1]
        ar = np.mean(recall) if recall.size else float("nan")
        per_class_AR[name] = float(ar * 100)

    num_cols = min(colums, len(per_class_AR) * len(headers))
    result_pair = [x for pair in per_class_AR.items() for x in pair]
    row_pair = itertools.zip_longest(*[result_pair[i::num_cols] for i in range(num_cols)])
    table_headers = headers * (num_cols // len(headers))
    table = tabulate(
        row_pair,
        tablefmt="pipe",
        floatfmt=".3f",
        headers=table_headers,
        numalign="left",
    )
    return table


def per_class_AP_table(coco_eval, class_names=COCO_CLASSES, headers=["class", "AP"], colums=6):
    per_class_AP = {}
    precisions = coco_eval.eval["precision"]
    # dimension of precisions: [TxRxKxAxM]
    # precision has dims (iou, recall, cls, area range, max dets)
    assert len(class_names) == precisions.shape[2]

    for idx, name in enumerate(class_names):
        # area range index 0: all area ranges
        # max dets index -1: typically 100 per image
        precision = precisions[:, :, idx, 0, -1]
        precision = precision[precision > -1]
        ap = np.mean(precision) if precision.size else float("nan")
        per_class_AP[name] = float(ap * 100)

    num_cols = min(colums, len(per_class_AP) * len(headers))
    result_pair = [x for pair in per_class_AP.items() for x in pair]
    row_pair = itertools.zip_longest(*[result_pair[i::num_cols] for i in range(num_cols)])
    table_headers = headers * (num_cols // len(headers))
    table = tabulate(
        row_pair,
        tablefmt="pipe",
        floatfmt=".3f",
        headers=table_headers,
        numalign="left",
    )
    return table


class COCOEvaluator(Evaler):

    def __init__(
        self,
        data,
        batch_size=1,
        img_size=1280,
        conf_thres=0.03,
        iou_thres=0.65,
        device="",
        half=True,
        save_dir="",
        shrink_size=1280,
        infer_on_rect=False,
        verbose=False,
        do_coco_metric=True,
        do_pr_metric=False,
        plot_curve=False,
        plot_confusion_matrix=False,
        specific_shape=False,
        height=1280,
        width=1280,
    ):
        super().__init__(
            data=data,
            batch_size=batch_size,
            img_size=img_size,
            conf_thres=conf_thres,
            iou_thres=iou_thres,
            device=device,
            half=half,
            save_dir=save_dir,
            shrink_size=shrink_size,
            infer_on_rect=infer_on_rect,
            verbose=verbose,
            do_coco_metric=do_coco_metric,
            do_pr_metric=do_pr_metric,
            plot_curve=plot_curve,
            plot_confusion_matrix=plot_confusion_matrix,
            specific_shape=specific_shape,
            height=height,
            width=width,
        )

    def predict_model(self, model: ov.CompiledModel, dataloader, task):
        """Model prediction
        Predicts the whole dataset and gets the prediced results and inference time.
        """
        self.speed_result = torch.zeros(4, device=self.device)
        pred_results = []
        pbar = tqdm(dataloader, desc=f"Inferencing model in {task} datasets.", ncols=NCOLS)

        # whether to compute metric and plot PR curve and P、R、F1 curve under iou50 match rule
        if self.do_pr_metric:
            stats, ap = [], []
            seen = 0
            iouv = torch.linspace(0.5, 0.95, 10)  # iou vector for mAP@0.5:0.95
            niou = iouv.numel()
            if self.plot_confusion_matrix:
                from yolov6.utils.metrics import ConfusionMatrix

                confusion_matrix = ConfusionMatrix(nc=model.nc)

        output_layer = model.output(0)

        for i, (imgs, targets, paths, shapes) in enumerate(pbar):
            # pre-process
            t1 = time_sync()
            imgs = imgs.to(self.device, non_blocking=True)
            imgs = imgs.half() if self.half else imgs.float()
            imgs /= 255
            self.speed_result[1] += time_sync() - t1  # pre-process time

            # Inference
            t2 = time_sync()
            outputs = model(imgs)[output_layer]
            outputs = torch.from_numpy(outputs)
            self.speed_result[2] += time_sync() - t2  # inference time

            # post-process
            t3 = time_sync()
            outputs = non_max_suppression(outputs, self.conf_thres, self.iou_thres, multi_label=True)
            self.speed_result[3] += time_sync() - t3  # post-process time
            self.speed_result[0] += len(outputs)

            if self.do_pr_metric:
                import copy

                eval_outputs = copy.deepcopy([x.detach().cpu() for x in outputs])

            # save result
            pred_results.extend(self.convert_to_coco_format(outputs, imgs, paths, shapes, self.ids))

            # for tensorboard visualization, maximum images to show: 8
            if i == 0:
                vis_num = min(len(imgs), 8)
                vis_outputs = outputs[:vis_num]
                vis_paths = paths[:vis_num]

            if not self.do_pr_metric:
                continue

            # Statistics per image
            # This code is based on
            # https://github.com/ultralytics/yolov5/blob/master/val.py
            for si, pred in enumerate(eval_outputs):
                labels = targets[targets[:, 0] == si, 1:]
                nl = len(labels)
                tcls = labels[:, 0].tolist() if nl else []  # target class
                seen += 1

                if len(pred) == 0:
                    if nl:
                        stats.append((torch.zeros(0, niou, dtype=torch.bool), torch.Tensor(), torch.Tensor(), tcls))
                    continue

                # Predictions
                predn = pred.clone()
                self.scale_coords(imgs[si].shape[1:], predn[:, :4], shapes[si][0], shapes[si][1])  # native-space pred

                # Assign all predictions as incorrect
                correct = torch.zeros(pred.shape[0], niou, dtype=torch.bool)
                if nl:

                    from yolov6.utils.nms import xywh2xyxy

                    # target boxes
                    tbox = xywh2xyxy(labels[:, 1:5])
                    tbox[:, [0, 2]] *= imgs[si].shape[1:][1]
                    tbox[:, [1, 3]] *= imgs[si].shape[1:][0]

                    self.scale_coords(imgs[si].shape[1:], tbox, shapes[si][0], shapes[si][1])  # native-space labels

                    labelsn = torch.cat((labels[:, 0:1], tbox), 1)  # native-space labels

                    from yolov6.utils.metrics import process_batch

                    correct = process_batch(predn, labelsn, iouv)
                    if self.plot_confusion_matrix:
                        confusion_matrix.process_batch(predn, labelsn)

                # Append statistics (correct, conf, pcls, tcls)
                stats.append((correct.cpu(), pred[:, 4].cpu(), pred[:, 5].cpu(), tcls))

        if self.do_pr_metric:
            # Compute statistics
            stats = [np.concatenate(x, 0) for x in zip(*stats)]  # to numpy
            if len(stats) and stats[0].any():

                from yolov6.utils.metrics import ap_per_class

                p, r, ap, f1, ap_class = ap_per_class(
                    *stats, plot=self.plot_curve, save_dir=self.save_dir, names=model.names
                )
                AP50_F1_max_idx = len(f1.mean(0)) - f1.mean(0)[::-1].argmax() - 1
                logger.info(f"IOU 50 best mF1 thershold near {AP50_F1_max_idx/1000.0}.")
                ap50, ap = ap[:, 0], ap.mean(1)  # AP@0.5, AP@0.5:0.95
                mp, mr, map50, map = p[:, AP50_F1_max_idx].mean(), r[:, AP50_F1_max_idx].mean(), ap50.mean(), ap.mean()
                nt = np.bincount(stats[3].astype(np.int64), minlength=model.nc)  # number of targets per class

                # Print results
                s = ("%-16s" + "%12s" * 7) % (
                    "Class",
                    "Images",
                    "Labels",
                    "P@.5iou",
                    "R@.5iou",
                    "F1@.5iou",
                    "mAP@.5",
                    "mAP@.5:.95",
                )
                logger.info(s)
                pf = "%-16s" + "%12i" * 2 + "%12.3g" * 5  # print format
                logger.info(pf % ("all", seen, nt.sum(), mp, mr, f1.mean(0)[AP50_F1_max_idx], map50, map))

                self.pr_metric_result = (map50, map)

                # Print results per class
                if self.verbose and model.nc > 1:
                    for i, c in enumerate(ap_class):
                        logger.info(
                            pf
                            % (
                                model.names[c],
                                seen,
                                nt[c],
                                p[i, AP50_F1_max_idx],
                                r[i, AP50_F1_max_idx],
                                f1[i, AP50_F1_max_idx],
                                ap50[i],
                                ap[i],
                            )
                        )

                if self.plot_confusion_matrix:
                    confusion_matrix.plot(save_dir=self.save_dir, names=list(model.names))
            else:
                logger.info("Calculate metric failed, might check dataset.")
                self.pr_metric_result = (0.0, 0.0)

        return pred_results, vis_outputs, vis_paths

    def eval_model(self, pred_results, task):
        """Evaluate models
        For task speed, this function only evaluates the speed of model and outputs inference time.
        For task val, this function evaluates the speed and mAP by pycocotools, and returns
        inference time and mAP value.
        """
        logger.info(f"\nEvaluating speed.")
        self.eval_speed(task)

        if not self.do_coco_metric and self.do_pr_metric:
            return self.pr_metric_result
        logger.info(f"\nEvaluating mAP by pycocotools.")
        if task != "speed" and len(pred_results):
            if "anno_path" in self.data:
                anno_json = self.data["anno_path"]
            else:
                # generated coco format labels in dataset initialization
                task = "val" if task == "train" else task
                if not isinstance(self.data[task], list):
                    self.data[task] = [self.data[task]]
                dataset_root = os.path.dirname(os.path.dirname(self.data[task][0]))
                base_name = os.path.basename(self.data[task][0])
                anno_json = os.path.join(dataset_root, "annotations", f"instances_{base_name}.json")
            pred_json = os.path.join(self.save_dir, "predictions.json")
            logger.info(f"Saving {pred_json}...")
            with open(pred_json, "w") as f:
                json.dump(pred_results, f)

            anno = COCO(anno_json)
            pred = anno.loadRes(pred_json)
            cocoEval = COCOeval(anno, pred, "bbox")
            # if self.is_coco:
            #     imgIds = [int(os.path.basename(x).split(".")[0]) for x in dataloader.dataset.img_paths]
            #     cocoEval.params.imgIds = imgIds
            cocoEval.evaluate()
            cocoEval.accumulate()

            # print each class ap from pycocotool result
            if self.verbose:

                import copy

                val_dataset_img_count = cocoEval.cocoGt.imgToAnns.__len__()
                val_dataset_anns_count = 0
                label_count_dict = {"images": set(), "anns": 0}
                label_count_dicts = [copy.deepcopy(label_count_dict) for _ in range(len(COCO_CLASSES))]
                for _, ann_i in cocoEval.cocoGt.anns.items():
                    if ann_i["ignore"]:
                        continue
                    val_dataset_anns_count += 1
                    nc_i = (
                        self.coco80_to_coco91_class().index(ann_i["category_id"])
                        if self.is_coco
                        else ann_i["category_id"]
                    )
                    label_count_dicts[nc_i]["images"].add(ann_i["image_id"])
                    label_count_dicts[nc_i]["anns"] += 1

                s = ("%-16s" + "%12s" * 7) % (
                    "Class",
                    "Labeled_images",
                    "Labels",
                    "P@.5iou",
                    "R@.5iou",
                    "F1@.5iou",
                    "mAP@.5",
                    "mAP@.5:.95",
                )
                logger.info(s)
                # IOU , all p, all cats, all gt, maxdet 100
                coco_p = cocoEval.eval["precision"]
                coco_p_all = coco_p[:, :, :, 0, 2]
                map = np.mean(coco_p_all[coco_p_all > -1])

                coco_p_iou50 = coco_p[0, :, :, 0, 2]
                map50 = np.mean(coco_p_iou50[coco_p_iou50 > -1])
                mp = np.array([np.mean(coco_p_iou50[ii][coco_p_iou50[ii] > -1]) for ii in range(coco_p_iou50.shape[0])])
                mr = np.linspace(0.0, 1.00, int(np.round((1.00 - 0.0) / 0.01)) + 1, endpoint=True)
                mf1 = 2 * mp * mr / (mp + mr + 1e-16)
                i = mf1.argmax()  # max F1 index

                pf = "%-16s" + "%12i" * 2 + "%12.3g" * 5  # print format
                logger.info(
                    pf % ("all", val_dataset_img_count, val_dataset_anns_count, mp[i], mr[i], mf1[i], map50, map)
                )

                # compute each class best f1 and corresponding p and r
                for nc_i in range(len(COCO_CLASSES)):
                    coco_p_c = coco_p[:, :, nc_i, 0, 2]
                    map = np.mean(coco_p_c[coco_p_c > -1])

                    coco_p_c_iou50 = coco_p[0, :, nc_i, 0, 2]
                    map50 = np.mean(coco_p_c_iou50[coco_p_c_iou50 > -1])
                    p = coco_p_c_iou50
                    r = np.linspace(0.0, 1.00, int(np.round((1.00 - 0.0) / 0.01)) + 1, endpoint=True)
                    f1 = 2 * p * r / (p + r + 1e-16)
                    i = f1.argmax()
                    logger.info(
                        pf
                        % (
                            COCO_CLASSES[nc_i],
                            len(label_count_dicts[nc_i]["images"]),
                            label_count_dicts[nc_i]["anns"],
                            p[i],
                            r[i],
                            f1[i],
                            map50,
                            map,
                        )
                    )
            cocoEval.summarize()
            map, map50 = cocoEval.stats[:2]  # update results (mAP@0.5:0.95, mAP@0.5)
            # Return results
            if task != "train":
                logger.info(f"Results saved to {self.save_dir}")
            return (map, map50)
        return (0.0, 0.0)

    def evaluate_prediction(self, data_dict, task):
        logger.info("Evaluate in main process...")

        logger.info(f"\nEvaluating speed.")
        self.eval_speed(task)

        if not self.do_coco_metric and self.do_pr_metric:
            return self.pr_metric_result

        info = "\n"

        # Evaluate the Dt (detection) json comparing with the ground truth
        if task != "speed" and len(data_dict) > 0:
            if "anno_path" in self.data:
                anno_json = self.data["anno_path"]
            else:
                # generated coco format labels in dataset initialization
                task = "val" if task == "train" else task
                if not isinstance(self.data[task], list):
                    self.data[task] = [self.data[task]]
                dataset_root = os.path.dirname(os.path.dirname(self.data[task][0]))
                base_name = os.path.basename(self.data[task][0])
                anno_json = os.path.join(dataset_root, "annotations", f"instances_{base_name}.json")

            pred_json = os.path.join(self.save_dir, "predictions.json")
            logger.info(f"Saving {pred_json}...")
            with open(pred_json, "w") as f:
                json.dump(data_dict, f)

            cocoGt = COCO(anno_json)
            cocoDt = cocoGt.loadRes(pred_json)

            logger.warning("Use standard COCOeval.")

            cocoEval = COCOeval(cocoGt, cocoDt, "bbox")
            cocoEval.evaluate()
            cocoEval.accumulate()
            redirect_string = io.StringIO()
            with contextlib.redirect_stdout(redirect_string):
                cocoEval.summarize()
            info += redirect_string.getvalue()
            cat_ids = list(cocoGt.cats.keys())
            cat_names = [cocoGt.cats[catId]["name"] for catId in sorted(cat_ids)]
            if self.verbose:
                AP_table = per_class_AP_table(cocoEval, class_names=cat_names)
                info += "per class AP:\n" + AP_table + "\n"
            if self.verbose:
                AR_table = per_class_AR_table(cocoEval, class_names=cat_names)
                info += "per class AR:\n" + AR_table + "\n"
            return cocoEval.stats[0], cocoEval.stats[1], info
        else:
            return 0, 0, info


def boolean_string(s):
    if s not in {"False", "True"}:
        raise ValueError("Not a valid boolean string")
    return s == "True"


def get_args_parser(add_help=True):
    parser = argparse.ArgumentParser(description="YOLOv6 PyTorch Evalating", add_help=add_help)
    parser.add_argument("--ov_model_path", type=str, default="./weights/yolov6s.xml", help="openvino model path")
    parser.add_argument("--data", type=str, default="./data/coco.yaml", help="dataset.yaml path")
    parser.add_argument("--weights", type=str, default="./weights/yolov6s.pt", help="model.pt path(s)")
    parser.add_argument("--batch-size", type=int, default=32, help="batch size")
    parser.add_argument("--img-size", type=int, default=1280, help="inference size (pixels)")
    parser.add_argument("--conf-thres", type=float, default=0.03, help="confidence threshold")
    parser.add_argument("--iou-thres", type=float, default=0.65, help="NMS IoU threshold")
    parser.add_argument("--task", default="val", help="val, test, or speed")
    parser.add_argument("--device", default="cpu", help="cuda device, i.e. 0 or 0,1,2,3 or cpu")
    parser.add_argument("--half", default=False, action="store_true", help="whether to use fp16 infer")
    parser.add_argument("--save_dir", type=str, default="runs/val/", help="evaluation save dir")
    parser.add_argument("--name", type=str, default="exp", help="save evaluation results to save_dir/name")
    parser.add_argument("--shrink_size", type=int, default=0, help="load img resize when test")
    parser.add_argument(
        "--infer_on_rect", default=True, type=boolean_string, help="default to run with rectangle image to boost speed."
    )
    parser.add_argument(
        "--reproduce_640_eval",
        default=False,
        action="store_true",
        help="whether to reproduce 640 infer result, overwrite some config",
    )
    parser.add_argument(
        "--eval_config_file",
        type=str,
        default="./configs/experiment/eval_640_repro.py",
        help="config file for repro 640 infer result",
    )
    parser.add_argument(
        "--do_coco_metric",
        default=True,
        type=boolean_string,
        help="whether to use pycocotool to metric, set False to close",
    )
    parser.add_argument(
        "--do_pr_metric",
        default=False,
        type=boolean_string,
        help="whether to calculate precision, recall and F1, n, set False to close",
    )
    parser.add_argument(
        "--plot_curve",
        default=True,
        type=boolean_string,
        help="whether to save plots in savedir when do pr metric, set False to close",
    )
    parser.add_argument(
        "--plot_confusion_matrix",
        default=False,
        action="store_true",
        help="whether to save confusion matrix plots when do pr metric, might cause no harm warning print",
    )
    parser.add_argument("--verbose", default=False, action="store_true", help="whether to print metric on each class")
    parser.add_argument(
        "--config-file",
        default="",
        type=str,
        help="experiments description file, lower priority than reproduce_640_eval",
    )
    parser.add_argument("--specific-shape", action="store_true", help="rectangular training")
    parser.add_argument("--height", type=int, default=1280, help="image height of model input")
    parser.add_argument("--width", type=int, default=1280, help="image width of model input")
    args = parser.parse_args()

    if args.config_file:
        assert os.path.exists(args.config_file), print("Config file {} does not exist".format(args.config_file))
        cfg = Config.fromfile(args.config_file)
        if not hasattr(cfg, "eval_params"):
            logger.info("Config file doesn't has eval params config.")
        else:
            eval_params = cfg.eval_params
            for key, value in eval_params.items():
                if key not in args.__dict__:
                    logger.info(f"Unrecognized config {key}, continue")
                    continue
                if isinstance(value, list):
                    if value[1] is not None:
                        args.__dict__[key] = value[1]
                else:
                    if value is not None:
                        args.__dict__[key] = value

    # load params for reproduce 640 eval result
    if args.reproduce_640_eval:
        assert os.path.exists(args.eval_config_file), print(
            "Reproduce config file {} does not exist".format(args.eval_config_file)
        )
        eval_params = Config.fromfile(args.eval_config_file).eval_params
        eval_model_name = os.path.splitext(os.path.basename(args.weights))[0]
        if eval_model_name not in eval_params:
            eval_model_name = "default"
        args.shrink_size = eval_params[eval_model_name]["shrink_size"]
        args.infer_on_rect = eval_params[eval_model_name]["infer_on_rect"]
        # force params
        args.conf_thres = 0.03
        args.iou_thres = 0.65
        args.task = "val"
        args.do_coco_metric = True

    logger.info(args)
    return args


def get_model_size(ir_path: Path, m_type: str = "Mb") -> float:
    xml_size = ir_path.stat().st_size
    bin_size = ir_path.with_suffix(".bin").stat().st_size
    for t in ["bytes", "Kb", "Mb"]:
        if m_type == t:
            break
        xml_size /= 1024
        bin_size /= 1024
    model_size = xml_size + bin_size
    logger.info(f"Model graph (xml):   {xml_size:.3f} {m_type}")
    logger.info(f"Model weights (bin): {bin_size:.3f} {m_type}")
    logger.info(f"Model size:          {model_size:.3f} {m_type}")
    return model_size


def prepare_openvino_model(ov_model_path) -> ov.Model:
    return ov.Core().read_model(ov_model_path)


def validate(
    model: ov.Model, data_loader: torch.utils.data.DataLoader, validator: COCOEvaluator, task: str
) -> Tuple[float, float, str]:

    model.reshape({0: [1, 3, -1, -1]})
    compiled_model = ov.compile_model(model, device_name="CPU")

    pred_result, vis_outputs, vis_paths = validator.predict_model(compiled_model, data_loader, task)
    # ap50_95, ap50 = validator.eval_model(pred_result, task)
    # summary = "\n"
    ap50_95, ap50, summary = validator.evaluate_prediction(pred_result, task)

    return ap50_95, ap50, summary


def quantize_ac(
    model: ov.Model, data_loader: torch.utils.data.DataLoader, validator_ac: COCOEvaluator, device: torch.device
) -> ov.Model:

    def transform_fn(data_item: Dict, device: torch.device) -> torch.Tensor:
        # Skip label and add a batch dimension to an image tensor
        images, _, _, _ = data_item
        images = images.to(device, non_blocking=True)
        images = images.half() if args.half else images.float()
        images /= 255
        return images

    def validation_ac(
        compiled_model: ov.CompiledModel,
        validation_loader: torch.utils.data.DataLoader,
        validator: COCOEvaluator,
        task: str,
    ) -> float:

        pred_result, vis_outputs, vis_paths = validator.predict_model(compiled_model, validation_loader, task)
        # ap50_95, ap50 = validator.eval_model(pred_result, task)
        # summary = "\n"
        ap50_95, ap50, summary = validator.evaluate_prediction(pred_result, task)

        logger.info(f"current mAP @ 0.5: {ap50:.3f}, mAP @ 0.5_0.95: {ap50_95:.3f}")

        return ap50_95

    quantization_dataset = nncf.Dataset(data_loader, partial(transform_fn, device=device))

    validation_fn = partial(validation_ac, validator=validator_ac, task="val")

    quantized_model_ac = nncf.quantize_with_accuracy_control(
        model,
        quantization_dataset,
        quantization_dataset,
        subset_size=len(data_loader),
        validation_fn=validation_fn,
        max_drop=0.010,
        preset=nncf.QuantizationPreset.MIXED,
        # ignored_scope=nncf.IgnoredScope(
        #     types=["Multiply", "Subtract", "Sigmoid"],  # ignore operations
        #     subgraphs=[
        #         nncf.Subgraph(
        #             inputs=[
        #                 "/model.22/Concat_3",
        #                 "/model.22/Concat_6",
        #                 "/model.22/Concat_5",
        #                 "/model.22/Concat_4",
        #             ],
        #             outputs=["output0"],
        #         )
        #     ],
        # ),
    )
    return quantized_model_ac


@torch.no_grad()
def run(
    data,
    weights=None,
    batch_size=32,
    img_size=1280,
    conf_thres=0.03,
    iou_thres=0.65,
    task="val",
    device="cpu",
    half=False,
    model=None,
    dataloader=None,
    save_dir="",
    name="",
    shrink_size=1280,
    letterbox_return_int=False,
    infer_on_rect=False,
    reproduce_640_eval=False,
    eval_config_file="./configs/experiment/eval_640_repro.py",
    verbose=False,
    do_coco_metric=True,
    do_pr_metric=False,
    plot_curve=False,
    plot_confusion_matrix=False,
    config_file=None,
    specific_shape=False,
    height=1280,
    width=1280,
    ov_model_path=None,
):
    """Run the evaluation process

    This function is the main process of evaluation, supporting image file and dir containing images.
    It has tasks of 'val', 'train' and 'speed'. Task 'train' processes the evaluation during training phase.
    Task 'val' processes the evaluation purely and return the mAP of model.pt. Task 'speed' processes the
    evaluation of inference speed of model.pt.

    """

    # task
    COCOEvaluator.check_task(task)
    if task == "train":
        save_dir = save_dir
    else:
        save_dir = str(increment_name(osp.join(save_dir, name)))
        os.makedirs(save_dir, exist_ok=True)

    # check the threshold value, reload device/half/data according task
    COCOEvaluator.check_thres(conf_thres, iou_thres, task)
    device = COCOEvaluator.reload_device(device, model, task)
    half = device.type != "cpu" and half
    data = COCOEvaluator.reload_dataset(data, task) if isinstance(data, str) else data

    # verify imgsz is gs-multiple
    if specific_shape:
        height = check_img_size(height, 32, floor=256)
        width = check_img_size(width, 32, floor=256)
    else:
        img_size = check_img_size(img_size, 32, floor=256)

    validator = COCOEvaluator(
        data,
        batch_size,
        img_size,
        conf_thres,
        iou_thres,
        device,
        half,
        save_dir,
        shrink_size,
        infer_on_rect,
        verbose,
        do_coco_metric,
        do_pr_metric,
        plot_curve,
        plot_confusion_matrix,
        specific_shape=specific_shape,
        height=height,
        width=width,
    )

    _ = validator.init_model(model, weights, task)
    val_dataloader = validator.init_data(dataloader, task)

    # Convert to OpenVINO model
    ov_model_path = Path(ov_model_path)

    ov_model = prepare_openvino_model(ov_model_path)
    fp32_model_size = get_model_size(ov_model_path)

    # Quantize mode in OpenVINO representation
    quantized_model = quantize_ac(ov_model, val_dataloader, validator, device)
    quantized_model_path = ov_model_path.with_name(ov_model_path.stem + "_quantized" + ov_model_path.suffix)
    ov.save_model(quantized_model, str(quantized_model_path))
    int8_model_size = get_model_size(quantized_model_path)

    # Validate FP32 model
    fp32_ap50_95, fp32_ap50, fp32_summary = validate(ov_model, val_dataloader, validator, task)
    logger.info("Floating-point model validation results:")
    logger.info(f"mAP @ 0.5: {fp32_ap50:.3f}, mAP @ 0.5_0.95: {fp32_ap50_95:.3f}")
    logger.info("\n" + fp32_summary)

    # Validate quantized model
    int8_ap50_95, int8_ap50, int8_summary = validate(quantized_model, val_dataloader, validator, task)
    logger.info("Quantized model validation results:")
    logger.info(f"mAP @ 0.5: {int8_ap50:.3f}, mAP @ 0.5_0.95: {int8_ap50_95:.3f}")
    logger.info("\n" + int8_summary)

    logger.info(f"mAP drop: {fp32_ap50 - int8_ap50:.3f}")
    logger.info(f"Model compression rate: {fp32_model_size / int8_model_size:.3f}")
    # https://docs.openvino.ai/latest/openvino_docs_optimization_guide_dldt_optimization_guide.html


def main(args):
    run(**vars(args))


if __name__ == "__main__":
    args = get_args_parser()
    main(args)

```



### For COCO dataset

Change the `COCO_CLASSES = ["bicycle", "car", "motorcycle", "bus", "truck"]` in `yolov6_quantization_with_accuracy_control.py` script to original classes of COCO dataset.

The  `yolov6_quantization_with_accuracy_control.py` script can be found in [For customized dataset](#for-customized-dataset).



##### Prepare quantization dataset

The original COCO dataset has too much data and is not suitable for use as a quantization dataset, so the coco128 dataset was used.

The coco128 dataset contains the first 128 images of COCO train 2017.  It is used as the tutorial dataset for YOLOv5: https://github.com/ultralytics/yolov5. It uses the same 128 images to train and test on. It is intended to validate a training pipeline by demonstrating overfitting on a small dataset before training a larger dataset. Here we use it as our quantization dataset.

```bash
curl -k -o coco128.zip https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip -L
unzip coco128.zip
```

The dataset structure is as follows:

```
├── coco128
│   ├── images
│   │   └── train2017
│   ├── labels
│   │   └── train2017
│   ├── LICENSE
│   ├── README.txt
```



Then use the following command to generate coco128 annotations files.

```bash
python3 generate_coco128_annotations.py --coco_dir /path/to/coco --coco128_dir /path/to/coco128 --output_json /path/to/coco128/annotations/instances_train2017.json
```

The final dataset structure is as follows:

```
├── coco128
│   ├── annotations
│   │   └── instances_train2017.json
│   ├── images
│   │   └── train2017
│   ├── labels
│   │   └── train2017
│   ├── LICENSE
│   ├── README.txt
```

The  `generate_coco128_annotations.py` script is as follows:

```python
import json
import os
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Filter COCO annotations for COCO128 subset.")
    parser.add_argument("--coco_dir", type=str, required=True, help="Path to the original COCO dataset directory")
    parser.add_argument("--coco128_dir", type=str, required=True, help="Path to the COCO128 dataset directory")
    parser.add_argument(
        "--output_json", type=str, required=True, help="Path to save the filtered COCO128 annotation JSON"
    )
    return parser.parse_args()


def get_coco128_image_filenames(coco128_images_dir):
    """Get the set of image filenames in COCO128 images directory."""
    image_filenames = set()
    for root, _, files in os.walk(coco128_images_dir):
        for file in files:
            if file.lower().endswith(".jpg"):
                image_filenames.add(file)
    return image_filenames


def filter_coco_annotations(coco_data, coco128_images):
    """Filter images and annotations for COCO128 subset."""
    filtered_images = []
    filtered_annotations = []
    image_id_set = set()
    annotation_id = 0

    # Build a mapping from image_id to image for quick lookup
    image_filename_to_id = {img["file_name"]: img["id"] for img in coco_data["images"]}

    # Filter images
    for image in coco_data["images"]:
        if image["file_name"] in coco128_images:
            filtered_images.append(image)
            image_id_set.add(image["id"])

    # Filter and re-index annotations
    for annotation in coco_data["annotations"]:
        if annotation["image_id"] in image_id_set:
            new_annotation = annotation.copy()
            new_annotation["id"] = annotation_id
            filtered_annotations.append(new_annotation)
            annotation_id += 1

    return filtered_images, filtered_annotations


def main():
    args = parse_args()

    coco_json_path = os.path.join(args.coco_dir, "annotations/instances_train2017.json")
    coco128_images_dir = os.path.join(args.coco128_dir, "images/train2017")

    # Load original COCO annotations
    with open(coco_json_path, "r") as f:
        coco_data = json.load(f)

    # Get COCO128 image filenames
    coco128_images = get_coco128_image_filenames(coco128_images_dir)

    # Filter images and annotations
    filtered_images, filtered_annotations = filter_coco_annotations(coco_data, coco128_images)

    # Create new JSON data
    filtered_data = {
        "info": coco_data.get("info", {}),
        "licenses": coco_data.get("licenses", []),
        "images": filtered_images,
        "annotations": filtered_annotations,
        "categories": coco_data.get("categories", []),
    }

    # Save filtered annotations
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, "w") as f:
        json.dump(filtered_data, f)
    print(f"Filtered annotation saved to {args.output_json}")


if __name__ == "__main__":
    main()
```



##### Prepare dataset yaml file

Prepare your own customized dataset yaml file `$YOLOv6_DIR/data/coco128.yaml` based on `$YOLOv6_DIR/data/coco.yaml`

```yaml
# COCO 2017 dataset http://cocodataset.org

# If you are using Windows system,
# the dataset path should be like this:
# train: d:\dataset\coco\images\train2017
# because windows use "\" as separator, linux use "/" as separator.

train: /paht/to/coco128/images/train2017 
val: /paht/to/coco128/images/train2017 
test: /paht/to/coco128/images/train2017
anno_path: /paht/to/coco128/annotations/instances_train2017.json

# number of classes
nc: 80
# whether it is coco dataset, only coco dataset should be set to True.
is_coco: True

# class names
names: [ 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
         'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
         'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
         'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
         'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
         'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
         'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
         'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
         'hair drier', 'toothbrush' ]

```



##### Quantization using coco128 dataset

Change the `COCO_CLASSES = ["bicycle", "car", "motorcycle", "bus", "truck"]` in `yolov6_quantization_with_accuracy_control.py` script to original classes of COCO dataset.

Then run the following command to do model quantization.

```bash
cd $YOLOv6_DIR

python3 yolov6_quantization_with_accuracy_control.py --ov_model_path ./weights/FP32/yolov6s.xml --data data/coco128.yaml --weights ./weights/yolov6s.pt --batch 1 --task val --device cpu --img-size 640 --height 640 --width 640 --specific-shape --verbose
```

After running the command, The quantized model will be located at `./weights/FP32/yolov6s_quantized.xml`.



## Run YOLOv6s model in TFCC pipeline

### Create detection model_proc file

You can refer to this file `$PROJ_DIR/ai_inference/deployment/models/how_to_create_detection_model_proc_file.md`.

Two examples are provided below:

##### For customized dataset

```json
{
    "json_schema_version": "1.2.0",
    "model_type": "detection",
    "model_input": {
        "format": {
            "format": "image",
            "layout": "NCHW",
            "precision": "U8"
        }
    },
    "model_output": {
        "format": {
            "layout": "B",
            "detection_output": {
                "size": 10,
                "bbox_format": "CENTER_SIZE",
                "location_index": [
                    0,
                    1,
                    2,
                    3
                ],
                "confidence_index": 4,
                "first_class_prob_index": 5
            }
        },
        "class_label_table": "coco"
    },
    "post_proc_output": {
        "function_name": "HVA_det_postproc",
        "format": {
            "bbox": "FLOAT_ARRAY",
            "label_id": "INT",
            "confidence": "FLOAT"
        },
        "process": [
            {
                "name": "bbox_transform",
                "params": {
                    "apply_to_layer": "ANY",
                    "target_type": "CORNER_SIZE",
                    "scale_h": 640,
                    "scale_w": 640,
                    "clip_normalized_rect": true
                }
            },
            {
                "name": "NMS",
                "params": {
                    "apply_to_layer": "ALL",
                    "iou_threshold": 0.5,
                    "class_agnostic": true
                }
            }
        ],
        "mapping": {
            "bbox": {
                "input": {
                    "index": [
                        0,
                        1,
                        2,
                        3
                    ]
                },
                "op": [
                    {
                        "name": "identity",
                        "params": {}
                    }
                ]
            },
            "label_id": {
                "input": {
                    "index": [
                        5,
                        6,
                        7,
                        8,
                        9
                    ]
                },
                "op": [
                    {
                        "name": "argmax",
                        "params": {}
                    }
                ]
            },
            "confidence": {
                "input": {
                    "index": [
                        4,
                        5,
                        6,
                        7,
                        8,
                        9
                    ]
                },
                "op": [
                    {
                        "name": "yolo_multiply",
                        "params": {}
                    }
                ]
            }
        }
    },
    "labels_table": [
        {
            "name": "coco",
            "labels": [
                "bicycle",
                "car",
                "motorcycle",
                "bus",
                "truck"
            ]
        }
    ]
}
```



##### For COCO dataset

```json
{
    "json_schema_version": "1.2.0",
    "model_type": "detection",
    "model_input": {
        "format": {
            "format": "image",
            "layout": "NCHW",
            "precision": "U8"
        }
    },
    "model_output": {
        "format": {
            "layout": "B",
            "detection_output": {
                "size": 85,
                "bbox_format": "CENTER_SIZE",
                "location_index": [
                    0,
                    1,
                    2,
                    3
                ],
                "confidence_index": 4,
                "first_class_prob_index": 5
            }
        },
        "class_label_table": "coco"
    },
    "post_proc_output": {
        "function_name": "HVA_det_postproc",
        "format": {
            "bbox": "FLOAT_ARRAY",
            "label_id": "INT",
            "confidence": "FLOAT"
        },
        "process": [
            {
                "name": "bbox_transform",
                "params": {
                    "apply_to_layer": "ANY",
                    "target_type": "CORNER_SIZE",
                    "scale_h": 640,
                    "scale_w": 640,
                    "clip_normalized_rect": true
                }
            },
            {
                "name": "NMS",
                "params": {
                    "apply_to_layer": "ALL",
                    "iou_threshold": 0.5,
                    "class_agnostic": true
                }
            }
        ],
        "mapping": {
            "bbox": {
                "input": {
                    "index": [
                        0,
                        1,
                        2,
                        3
                    ]
                },
                "op": [
                    {
                        "name": "identity",
                        "params": {}
                    }
                ]
            },
            "label_id": {
                "input": {
                    "index": [
                        5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                        21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
                        36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50,
                        51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
                        66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80,
                        81, 82, 83, 84
                    ]
                },
                "op": [
                    {
                        "name": "argmax",
                        "params": {}
                    }
                ]
            },
            "confidence": {
                "input": {
                    "index": [
                        4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                        21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
                        36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50,
                        51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
                        66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80,
                        81, 82, 83, 84
                    ]
                },
                "op": [
                    {
                        "name": "yolo_multiply",
                        "params": {}
                    }
                ]
            }
        }
    },
    "labels_table": [
        {
            "name": "coco",
            "labels": [
                "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
                "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
                "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
                "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
                "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
                "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
                "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", 
                "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", 
                "scissors", "teddy bear", "hair drier", "toothbrush"
            ]
        }
    ]
}
```



### Pipeline configs

The following shows how to support the yolov6s model in the pipeline config file:

```
{
    "Node Class Name": "DetectionNode",
    "Node Name": "Detection",
    "Thread Number": "1",
    "Is Source Node": "false",
    "Configure String": "InferReqNumber=(INT)6;PreProcessType=(STRING)vaapi-surface-sharing;reshapeWidth=(INT)640;reshapeHeight=(INT)640;Device=(STRING)GPU.0;InferConfig=(STRING_ARRAY)[PERFORMANCE_HINT=LATENCY];PreProcessConfig=(STRING_ARRAY)[VAAPI_THREAD_POOL_SIZE=6,VAAPI_FAST_SCALE_LOAD_FACTOR=0,SCALE_FACTOR=255.0];ModelPath=(STRING)vehicle-bike-detection-yolov6s-001/yolov6s.xml;ModelProcConfPath=(STRING)vehicle-bike-detection-yolov6s-001/yolov6s.model_proc.json;Threshold=(FLOAT)0.3;MaxROI=(INT)0;FilterLabels=(STRING_ARRAY)[car,bus,truck]"
}
```

The key point is to add the parameter `SCALE_FACTOR=255.0` and then specify the `ModelPath` and `ModelProcConfPath`.

