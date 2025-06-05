from ultralytics import YOLO
import os
import json
import cv2
import argparse
from PIL import Image, ImageFile
import os.path as osp
from typing import Any
import errno
import torchvision


ImageFile.LOAD_TRUNCATED_IMAGES = True

parser = argparse.ArgumentParser(description="Raddet dataset automatic annatation using YOLO model.")
parser.add_argument("--model", type=str, default="yolov10x.pt", help="selected model.")
parser.add_argument("--img_dir", type=str, help="input image file folder.")
parser.add_argument("--out_dir", type=str, default="gt", help="output label file folder.")
parser.add_argument("--vis_dir", type=str, default="vis", help="folder for visualize the image with bbox.")

# Set the categories to detect
TARGET_CLASSES = ["car", "truck", "bus", "motorcycle", "bicycle", "person"]
CLASSES_TO_ID = {"car": 0, "truck": 1, "bus": 2, "motorcycle": 3, "bicycle": 4, "person": 5}


def main(args):
    """
    Main function for automatic annotation using the YOLO model.

    This function loads a specified YOLO model and processes images from a given directory
    to detect objects belonging to predefined target classes. The detected objects are then
    labeled and saved in COCO format in a specified output directory. Additionally, the
    function generates visualizations of the detections and saves them in a separate directory.

    Parameters:
    args (argparse.Namespace): Command-line arguments containing the following attributes:
        - model (str): Path to the YOLO model file.
        - img_dir (str): Directory containing input images to be processed.
        - out_dir (str): Directory where label files will be saved.
        - vis_dir (str): Directory where visualization images will be saved.

    The function assumes that the input images are JPEG files and that the model labels
    detected objects with class IDs that can be mapped to the target classes defined
    in the TARGET_CLASSES list.
    """
    # Loading the YOLO model
    model = YOLO(args.model)

    image_dir = args.img_dir
    output_dir = args.out_dir
    vis_dir = args.vis_dir  # save visualization images

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(vis_dir, exist_ok=True)

    # Detect each image and save the label
    for image_name in os.listdir(image_dir):
        image_path = os.path.join(image_dir, image_name)
        results = model(image_path)

        # Save labels to coco format
        labels = ""
        for result in results:
            for box in result.boxes:
                label_name = model.names[int(box.cls)]
                if label_name in TARGET_CLASSES:
                    new_box = box.xywhn.tolist()[0]  # Actually is cxcywhn
                    label = "{} {} {} {} {}\n".format(
                        CLASSES_TO_ID[label_name], new_box[0], new_box[1], new_box[2], new_box[3]
                    )
                    labels += label

        # Save labels to file
        label_file = os.path.join(output_dir, os.path.splitext(image_name)[0] + ".txt")
        with open(label_file, "w") as f:
            f.write(labels)

        # visualization
        result_image = result.plot()
        result_image_path = os.path.join(vis_dir, image_name)
        cv2.imwrite(result_image_path, result_image)


if __name__ == "__main__":
    args = parser.parse_args()
    main(args)
