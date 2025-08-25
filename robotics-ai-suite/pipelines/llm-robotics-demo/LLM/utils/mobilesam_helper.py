# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor
import torch
import sys
import numpy as np
import cv2
import time
import openvino as ov
from PIL import Image
import os
from transformers import CLIPProcessor, CLIPModel
import torch.nn.functional as F

from segment_anything.utils.amg import (
    MaskData,
    generate_crop_boxes,
    uncrop_boxes_xyxy,
    uncrop_masks,
    uncrop_points,
    calculate_stability_score,
    rle_to_mask,
    batched_mask_to_box,
    mask_to_rle_pytorch,
    is_box_near_crop_edge,
    batch_iterator,
    remove_small_regions,
    build_all_layer_point_grids,
    box_xyxy_to_xywh,
    area_from_rle,
)
from torchvision.ops.boxes import batched_nms, box_area
from typing import Tuple, List, Dict, Any
from copy import deepcopy
from typing import Tuple
from torchvision.transforms.functional import resize, to_pil_image
from tqdm.notebook import tqdm

class ResizeLongestSide:
    """
    Resizes images to longest side 'target_length', as well as provides
    methods for resizing coordinates and boxes. Provides methods for
    transforming numpy arrays.
    """

    def __init__(self, target_length: int) -> None:
        self.target_length = target_length

    def apply_image(self, image: np.ndarray) -> np.ndarray:
        """
        Expects a numpy array with shape HxWxC in uint8 format.
        """
        target_size = self.get_preprocess_shape(image.shape[0], image.shape[1], self.target_length)
        return np.array(resize(to_pil_image(image), target_size))

    def apply_coords(self, coords: np.ndarray, original_size: Tuple[int, ...]) -> np.ndarray:
        """
        Expects a numpy array of length 2 in the final dimension. Requires the
        original image size in (H, W) format.
        """
        old_h, old_w = original_size
        new_h, new_w = self.get_preprocess_shape(original_size[0], original_size[1], self.target_length)
        coords = deepcopy(coords).astype(float)
        coords[..., 0] = coords[..., 0] * (new_w / old_w)
        coords[..., 1] = coords[..., 1] * (new_h / old_h)
        return coords

    def apply_boxes(self, boxes: np.ndarray, original_size: Tuple[int, ...]) -> np.ndarray:
        """
        Expects a numpy array shape Bx4. Requires the original image size
        in (H, W) format.
        """
        boxes = self.apply_coords(boxes.reshape(-1, 2, 2), original_size)
        return boxes.reshape(-1, 4)

    @staticmethod
    def get_preprocess_shape(oldh: int, oldw: int, long_side_length: int) -> Tuple[int, int]:
        """
        Compute the output size given input size and target long side length.
        """
        scale = long_side_length * 1.0 / max(oldh, oldw)
        newh, neww = oldh * scale, oldw * scale
        neww = int(neww + 0.5)
        newh = int(newh + 0.5)
        return (newh, neww)

class MobileSamHelper():
    debug = False
    clip_model_path = f"/home/intel/ov_models/clip-vit-base-patch16.xml"
    ov_sam_encoder_path = f"/home/intel/ov_models/sam_image_encoder.xml"
    ov_sam_predictor_path = f"/home/intel/ov_models/sam_mask_predictor.xml"
    sam_model_name = f"SAM"
    clip_model_name = f"openai/clip-vit-base-patch16"
    
    def __init__(self, label=None, sam_device='CPU', clip_device='CPU') -> None:
        core = ov.Core()
        self.sam_device = sam_device
        self.clip_device = clip_device
        self.label = label
        self.color_image = []
        self.resizer = ResizeLongestSide(1024)
        print(f"Loading sam model : {self.sam_model_name} to {self.sam_device}...")
        self.ov_encoder = core.compile_model(self.ov_sam_encoder_path, self.sam_device)
        self.ov_predictor = core.compile_model(self.ov_sam_predictor_path, self.sam_device)
        print(f"Loading clip model : {self.clip_model_name} to {self.clip_device}...")
        #self.clip = CLIPModel.from_pretrained(self.clip_model_name)
        self.compiled_clip = core.compile_model(self.clip_model_path, self.clip_device)
        # load preprocessor for model input
        print(f"Loading clip model processor: {self.clip_model_name}...")
        self.clip_processor = CLIPProcessor.from_pretrained(self.clip_model_name)
        print(f"MobileSamHelper init done...")

    def preprocess_image(self, image: np.ndarray):
        resized_image = self.resizer.apply_image(image)
        resized_image = (resized_image.astype(np.float32) - [123.675, 116.28, 103.53]) / [
            58.395,
            57.12,
            57.375,
        ]
        resized_image = np.expand_dims(np.transpose(resized_image, (2, 0, 1)).astype(np.float32), 0)

        # Pad
        h, w = resized_image.shape[-2:]
        padh = 1024 - h
        padw = 1024 - w
        x = np.pad(resized_image, ((0, 0), (0, 0), (0, padh), (0, padw)))
        return x
    
    def postprocess_masks(self, masks: np.ndarray, orig_size):
        size_before_pad = self.resizer.get_preprocess_shape(orig_size[0], orig_size[1], masks.shape[-1])
        masks = masks[..., : int(size_before_pad[0]), : int(size_before_pad[1])]
        masks = torch.nn.functional.interpolate(torch.from_numpy(masks), size=orig_size, mode="bilinear", align_corners=False).numpy()
        return masks

    def process_batch(self,
        image_embedding: np.ndarray,
        points: np.ndarray,
        im_size: Tuple[int, ...],
        crop_box: List[int],
        orig_size: Tuple[int, ...],
        iou_thresh,
        mask_threshold,
        stability_score_offset,
        stability_score_thresh,
    ) -> MaskData:
        orig_h, orig_w = orig_size

        # Run model on this batch
        transformed_points = self.resizer.apply_coords(points, im_size)
        in_points = transformed_points
        in_labels = np.ones(in_points.shape[0], dtype=int)

        inputs = {
            "image_embeddings": image_embedding,
            "point_coords": in_points[:, None, :],
            "point_labels": in_labels[:, None],
        }
        res = self.ov_predictor(inputs)
        masks = self.postprocess_masks(res[self.ov_predictor.output(0)], orig_size)
        masks = torch.from_numpy(masks)
        iou_preds = torch.from_numpy(res[self.ov_predictor.output(1)])

        # Serialize predictions and store in MaskData
        data = MaskData(
            masks=masks.flatten(0, 1),
            iou_preds=iou_preds.flatten(0, 1),
            points=torch.as_tensor(points.repeat(masks.shape[1], axis=0)),
        )
        del masks

        # Filter by predicted IoU
        if iou_thresh > 0.0:
            keep_mask = data["iou_preds"] > iou_thresh
            data.filter(keep_mask)

        # Calculate stability score
        data["stability_score"] = calculate_stability_score(data["masks"], mask_threshold, stability_score_offset)
        if stability_score_thresh > 0.0:
            keep_mask = data["stability_score"] >= stability_score_thresh
            data.filter(keep_mask)

        # Threshold masks and calculate boxes
        data["masks"] = data["masks"] > mask_threshold
        data["boxes"] = batched_mask_to_box(data["masks"])

        # Filter boxes that touch crop boundaries
        keep_mask = ~is_box_near_crop_edge(data["boxes"], crop_box, [0, 0, orig_w, orig_h])
        if not torch.all(keep_mask):
            data.filter(keep_mask)

        # Compress to RLE
        data["masks"] = uncrop_masks(data["masks"], crop_box, orig_h, orig_w)
        data["rles"] = mask_to_rle_pytorch(data["masks"])
        del data["masks"]

        return data

    def process_crop(self,
        image: np.ndarray,
        point_grids,
        crop_box: List[int],
        crop_layer_idx: int,
        orig_size: Tuple[int, ...],
        box_nms_thresh: float = 0.7,
        mask_threshold: float = 0.0,
        points_per_batch: int = 64,
        pred_iou_thresh: float = 0.88,
        stability_score_thresh: float = 0.95,
        stability_score_offset: float = 1.0,
    ) -> MaskData:
        # Crop the image and calculate embeddings
        x0, y0, x1, y1 = crop_box
        cropped_im = image[y0:y1, x0:x1, :]
        cropped_im_size = cropped_im.shape[:2]
        preprocessed_cropped_im = self.preprocess_image(cropped_im)
        crop_embeddings = self.ov_encoder(preprocessed_cropped_im)[self.ov_encoder.output(0)]

        # Get points for this crop
        points_scale = np.array(cropped_im_size)[None, ::-1]
        points_for_image = point_grids[crop_layer_idx] * points_scale

        # Generate masks for this crop in batches
        data = MaskData()
        for (points,) in batch_iterator(points_per_batch, points_for_image):
            batch_data = self.process_batch(
                crop_embeddings,
                points,
                cropped_im_size,
                crop_box,
                orig_size,
                pred_iou_thresh,
                mask_threshold,
                stability_score_offset,
                stability_score_thresh,
            )
            data.cat(batch_data)
            del batch_data

        # Remove duplicates within this crop.
        keep_by_nms = batched_nms(
            data["boxes"].float(),
            data["iou_preds"],
            torch.zeros(len(data["boxes"])),  # categories
            iou_threshold=box_nms_thresh,
        )
        data.filter(keep_by_nms)

        # Return to the original image frame
        data["boxes"] = uncrop_boxes_xyxy(data["boxes"], crop_box)
        data["points"] = uncrop_points(data["points"], crop_box)
        data["crop_boxes"] = torch.tensor([crop_box for _ in range(len(data["rles"]))])

        return data

    def generate_masks(self, image: np.ndarray, point_grids, crop_n_layers, crop_overlap_ratio, crop_nms_thresh) -> MaskData:
        orig_size = image.shape[:2]
        crop_boxes, layer_idxs = generate_crop_boxes(orig_size, crop_n_layers, crop_overlap_ratio)

        # Iterate over image crops
        data = MaskData()
        for crop_box, layer_idx in zip(crop_boxes, layer_idxs):
            crop_data = self.process_crop(image, point_grids, crop_box, layer_idx, orig_size)
            data.cat(crop_data)

        # Remove duplicate masks between crops
        if len(crop_boxes) > 1:
            # Prefer masks from smaller crops
            scores = 1 / box_area(data["crop_boxes"])
            scores = scores.to(data["boxes"].device)
            keep_by_nms = batched_nms(
                data["boxes"].float(),
                scores,
                torch.zeros(len(data["boxes"])),  # categories
                iou_threshold=crop_nms_thresh,
            )
            data.filter(keep_by_nms)

        data.to_numpy()
        return data

    def postprocess_small_regions(self, mask_data: MaskData, min_area: int, nms_thresh: float) -> MaskData:
        """
        Removes small disconnected regions and holes in masks, then reruns
        box NMS to remove any new duplicates.

        Edits mask_data in place.

        Requires open-cv as a dependency.
        """
        if len(mask_data["rles"]) == 0:
            return mask_data

        # Filter small disconnected regions and holes
        new_masks = []
        scores = []
        for rle in mask_data["rles"]:
            mask = rle_to_mask(rle)

            mask, changed = remove_small_regions(mask, min_area, mode="holes")
            unchanged = not changed
            mask, changed = remove_small_regions(mask, min_area, mode="islands")
            unchanged = unchanged and not changed

            new_masks.append(torch.as_tensor(mask).unsqueeze(0))
            # Give score=0 to changed masks and score=1 to unchanged masks
            # so NMS will prefer ones that didn't need postprocessing
            scores.append(float(unchanged))

        # Recalculate boxes and remove any new duplicates
        masks = torch.cat(new_masks, dim=0)
        boxes = batched_mask_to_box(masks)
        keep_by_nms = batched_nms(
            boxes.float(),
            torch.as_tensor(scores),
            torch.zeros(len(boxes)),  # categories
            iou_threshold=nms_thresh,
        )

        # Only recalculate RLEs for masks that have changed
        for i_mask in keep_by_nms:
            if scores[i_mask] == 0.0:
                mask_torch = masks[i_mask].unsqueeze(0)
                mask_data["rles"][i_mask] = mask_to_rle_pytorch(mask_torch)[0]
                # update res directly
                mask_data["boxes"][i_mask] = boxes[i_mask]
        mask_data.filter(keep_by_nms)

        return mask_data
    
    def automatic_mask_generation(self,
        image: np.ndarray,
        min_mask_region_area: int = 0,
        points_per_side: int = 32,
        crop_n_layers: int = 0,
        crop_n_points_downscale_factor: int = 1,
        crop_overlap_ratio: float = 512 / 1500,
        box_nms_thresh: float = 0.7,
        crop_nms_thresh: float = 0.9,
    ) -> List[Dict[str, Any]]:
        """
        Generates masks for the given image.

        Arguments:
        image (np.ndarray): The image to generate masks for, in HWC uint8 format.

        Returns:
        list(dict(str, any)): A list over records for masks. Each record is
            a dict containing the following keys:
            segmentation (dict(str, any) or np.ndarray): The mask. If
                output_mode='binary_mask', is an array of shape HW. Otherwise,
                is a dictionary containing the RLE.
            bbox (list(float)): The box around the mask, in XYWH format.
            area (int): The area in pixels of the mask.
            predicted_iou (float): The model's own prediction of the mask's
                quality. This is filtered by the pred_iou_thresh parameter.
            point_coords (list(list(float))): The point coordinates input
                to the model to generate this mask.
            stability_score (float): A measure of the mask's quality. This
                is filtered on using the stability_score_thresh parameter.
            crop_box (list(float)): The crop of the image used to generate
                the mask, given in XYWH format.
        """
        point_grids = build_all_layer_point_grids(
            points_per_side,
            crop_n_layers,
            crop_n_points_downscale_factor,
        )
        mask_data = self.generate_masks(image, point_grids, crop_n_layers, crop_overlap_ratio, crop_nms_thresh)

        # Filter small disconnected regions and holes in masks
        if min_mask_region_area > 0:
            mask_data = self.postprocess_small_regions(
                mask_data,
                min_mask_region_area,
                max(box_nms_thresh, crop_nms_thresh),
            )

        mask_data["segmentations"] = [rle_to_mask(rle) for rle in mask_data["rles"]]

        # Write mask records
        curr_anns = []
        for idx in range(len(mask_data["segmentations"])):
            ann = {
                "segmentation": mask_data["segmentations"][idx],
                "area": area_from_rle(mask_data["rles"][idx]),
                "bbox": box_xyxy_to_xywh(mask_data["boxes"][idx]).tolist(),
                "predicted_iou": mask_data["iou_preds"][idx].item(),
                "point_coords": [mask_data["points"][idx].tolist()],
                "stability_score": mask_data["stability_score"][idx].item(),
                "crop_box": box_xyxy_to_xywh(mask_data["crop_boxes"][idx]).tolist(),
            }
            curr_anns.append(ann)
        return curr_anns

    def get_result_image(self, anns, idx):
        if len(anns) == 0:
            return
        image = self.color_image.copy()
        #to opencv image
        cv2_im = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        obj = anns[idx]
        bbox = obj['bbox']  #XYWH
        left = bbox[0]-2
        top = bbox[1]-2
        right = bbox[0] + bbox[2]+2
        bottom = bbox[1] + bbox[3]+2
        # Red color in BGR
        color = (0, 0, 255)
        # Line thickness of 4 px
        thickness = 4
        bounding_result = cv2.rectangle(cv2_im, (left, top), (right, bottom), color, thickness)
        return bounding_result

    def draw_anns(self, image, anns):
        if len(anns) == 0:
            return
        segments_image = image.copy()
        sorted_anns = sorted(anns, key=(lambda x: x["area"]), reverse=True)
        for ann in tqdm(sorted_anns):
            mask = ann["segmentation"]
            mask_color = np.random.randint(0, 255, size=(1, 1, 3)).astype(np.uint8)
            segments_image[mask] = mask_color
        return cv2.addWeighted(image.astype(np.float32), 0.7, segments_image.astype(np.float32), 0.3, 0.0)

    def save_bbox(self, anns):
        if len(anns) == 0:
            return
        image = self.color_image

        out_dir = '/home/intel/qiudan/llm-robotics-demo-main/LLM/objects'
        print(f"Saving bbox images to =>{out_dir}")
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        else:
            for filename in os.listdir(out_dir):
                file_path = os.path.join(out_dir, filename)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f'Error: {e}')
        #image = Image.open(self.im_path)
        #input_im = []
        idx = 0
        for obj in anns:
            bbox = obj['bbox']  #XYWH
            x0 = bbox[0]
            y0 = bbox[1]
            x1 = bbox[0] + bbox[2]
            y1 = bbox[1] + bbox[3]
            rec = [x0, y0, x1, y1]
            crop_rectangle = image[y0:y1, x0:x1]
            cropped_im = Image.fromarray(crop_rectangle)
            idx += 1
            predicted_iou = obj['predicted_iou']
            stability_score = obj['stability_score']
            #print(f'crop{idx}.png=> predicted_iou = {predicted_iou}, stability_score = {stability_score}')
            #print(f'crop{idx}.png=> rec = {rec}')
            file_name = f'crop{idx}.png'
            image_path = os.path.join(out_dir, file_name)
            cropped_im.save(image_path)
            
            
    def save_predict_bbox(self, anns, idx):
        if len(anns) == 0:
            return
        image = self.color_image

        out_dir = '/home/intel/qiudan/llm-robotics-demo-main/LLM/predict_objects'
        print(f"Saving bbox images to =>{out_dir}")
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        else:
            for filename in os.listdir(out_dir):
                file_path = os.path.join(out_dir, filename)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f'Error: {e}')
        
        obj = anns[idx]
        bbox = obj['bbox']  #XYWH
        x0 = bbox[0]
        y0 = bbox[1]
        x1 = bbox[0] + bbox[2]
        y1 = bbox[1] + bbox[3]
        rec = [x0, y0, x1, y1]
        crop_rectangle = image[y0:y1, x0:x1]
        cropped_im = Image.fromarray(crop_rectangle)
        predicted_iou = obj['predicted_iou']
        stability_score = obj['stability_score']
        #print(f'crop{idx}.png=> predicted_iou = {predicted_iou}, stability_score = {stability_score}')
        #print(f'crop{idx}.png=> rec = {rec}')
        file_name = f'predict.png'
        image_path = os.path.join(out_dir, file_name)
        cropped_im.save(image_path)
            
            
    #remove duplicate areas
    def filter(self, anns):
        pass

    def calculate_centroid(self, bbox_list):
        x_min = bbox_list[0]
        y_min = bbox_list[1]
        x_max = bbox_list[2]
        y_max = bbox_list[3]
        x_mid = (x_max - x_min)/2 + x_min
        y_mid = (y_max - y_min)/2 + y_min
        return (int(x_mid), int(y_mid)), (((x_max - x_min)/2), ((y_max - y_min)/2))
    
    def clip_predict(self, anns):
        input_im = []
        if self.label == None:
            print(f'clip_predict error!! No input image or label!!')
            return None
        
        image = self.color_image.copy()
        print(f"clip_predict=> color_image.shape={image.shape}")
        for obj in anns:
            bbox = obj['bbox']  #XYWH
            x0 = bbox[0]
            y0 = bbox[1]
            x1 = bbox[0] + bbox[2]
            y1 = bbox[1] + bbox[3]
            crop_rectangle = image[y0:y1, x0:x1]
            #crop_rectangle = np.asanyarray(rec)
            #cropped_im = image.crop(crop_rectangle)
            cropped_im = Image.fromarray(crop_rectangle)
            #print(f"clip_predict=> cropped_im={cropped_im}")
            #print(f"clip_predict=> crop_rectangle={crop_rectangle}")
            input_im.append(cropped_im)
        
        
        input_labels = self.label
        text_descriptions = f"A photo of {input_labels}"
        inputs = self.clip_processor(text=text_descriptions, images=input_im, return_tensors="pt", padding=True)
        print(f'Start running ov clip...{self.clip_model_name}, prompt:{text_descriptions}')
        start = time.perf_counter()
        ov_logits_per_image = self.compiled_clip(dict(inputs))[0]
        end = time.perf_counter()
        delta = end - start
        print(f'Complete running ov clip, time: {delta*1000} ms')
        ov_output = ov_logits_per_image.reshape(-1)
        src = torch.Tensor(ov_output)
        ov_probs = F.softmax(src, dim=0)*100  #to score
        ov_probs = ov_probs.detach().cpu().numpy().reshape(-1)
        np.set_printoptions(formatter={'float': '{: 0.4f}'.format})
        print(f'ov Similarity: {ov_output}')
        print(f'ov prob: {ov_probs}')
        max_idx = np.argmax(ov_output)
        return max_idx, ov_output[max_idx], ov_probs[max_idx]
                                                                 
    def mask_everything(self):
        if len(self.color_image) == 0:
            print(f'mask_everything error!! No input image!!')
            return None
        print(f'Start running {self.sam_model_name} on {self.sam_device}')
        start = time.perf_counter()
        prediction = self.automatic_mask_generation(self.color_image, points_per_side=12)
        end = time.perf_counter()
        delta = end - start
        print(f'Complete running {self.sam_model_name}, time: {delta*1000} ms')
        print(f"Number of detected masks: {len(prediction)}")
        #out = self.draw_anns(image, prediction)
        #cv2.imwrite("result.png", out[:, :, ::-1])
        return prediction

    def test_bbox_clip(self):
        print("=======test_bbox_clip start==>")
        image_dir = '/home/intel/qiudan/llm-robotics-demo-main/LLM/objects'
        if not os.path.exists(image_dir):
            return None
        cnt = len(os.listdir(image_dir))
        input_im = []
        for idx in range(1, cnt+1):
            # 拼接图片路径
            file_name = f'crop{idx}.png'
            image_path = os.path.join(image_dir, file_name)
            # 使用PIL库读取图片
            image = Image.open(image_path)
            input_im.append(image)

        input_labels = self.label
        text_descriptions = f"A photo of {input_labels}"
        inputs = self.clip_processor(text=text_descriptions, images=input_im, return_tensors="pt", padding=True)
        print(f'Start running ov clip...{self.clip_model_name}, prompt:{text_descriptions}')
        start = time.perf_counter()
        ov_logits_per_image = self.compiled_clip(dict(inputs))[0]
        end = time.perf_counter()
        delta = end - start
        print(f'Complete running ov clip, time: {delta*1000} ms')
        ov_output = ov_logits_per_image.reshape(-1)
        src = torch.Tensor(ov_output)
        ov_probs = F.softmax(src, dim=0)*100  #to score
        ov_probs = ov_probs.detach().cpu().numpy().reshape(-1)
        
        np.set_printoptions(formatter={'float': '{: 0.4f}'.format})
        print(f'ov Similarity: {ov_output}')
        print(f'ov prob: {ov_probs}')
        print("========test_bbox_clip complete==>")
        

def test(color_image):

    image = color_image
    print(f"image=>{type(image)}")
    print(f"image=>{image.shape}")

    out_dir = 'objects-test'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    rec = [233, 12, 417, 204]
    x0 = rec[0]
    y0 = rec[1]
    x1 = rec[2]
    y1 = rec[3]
            
    crop_rectangle = image[y0:y1, x0:x1]
    #print(crop_rectangle)
    print(crop_rectangle.shape)
    cropped_im = Image.fromarray(crop_rectangle)
    save_name = './'+ out_dir + '/crop_test.jpg'
    cropped_im.save(save_name)

if __name__ == "__main__":
    im_path = f'/home/intel/qiudan/llm-robotics-demo-main/LLM/images/cam_output.jpg'
    label = 'the computer mouse'
    device = 'CPU'
    image = Image.open(im_path)
    color_image = np.asanyarray(image).copy()
    #test(color_image)
    helper = MobileSamHelper(device=device)
    helper.label = label
    helper.color_image = color_image
    helper.test_bbox_clip()
    '''
    #if debug
    #helper.debug = True
    masks = helper.mask_everything()
    if masks != None:
        max_idx, max_similarity, max_prob = helper.clip_predict(masks)
        #helper.save_bbox(masks)
        print(f'max_idx={max_idx}, max_similarity={max_similarity}, max_prob={max_prob}')
        #helper.test_bbox_clip()
    
    roi = masks[max_idx]['bbox']  #x, y, w, h
    center_box = helper.calculate_centroid([roi[0], roi[1], roi[0] + roi[2], roi[1] + roi[3]]) 
    object_centroid = center_box[0]
    objectxy = (roi[0], roi[1])
    resultImage = None
    confid_score = max_prob*100
    print(f"roi=>{roi}, object_centroid=>{object_centroid}, objectxy=>{objectxy}, confid_score=>{confid_score}")
    '''
    sys.exit(0)  
