import argparse
import os

import mmcv
import numpy as np
import torch
from mmcv import Config
from mmcv.cnn import fuse_conv_bn
# from mmcv.parallel import MMDistributedDataParallel
from mmcv.parallel import MMDataParallel, MMDistributedDataParallel
from mmcv.runner import load_checkpoint
from torchpack import distributed as dist
from torchpack.utils.config import configs
from torchpack.utils.tqdm import tqdm

from mmdet3d.apis import single_gpu_test
from mmdet.apis import multi_gpu_test, set_random_seed
from mmdet3d.core import LiDARInstance3DBoxes
from mmdet3d.core.utils import visualize_camera, visualize_lidar, visualize_map
from mmdet3d.datasets import build_dataloader, build_dataset
from mmdet3d.models import build_model
from mmdet3d.utils import get_root_logger, convert_sync_batchnorm, recursive_eval
# import tinyq
from functools import partial
from mmdet3d.datasets.v2x_dataset import collate_fn


def main() -> None:

    # dist.init()
    # tinyq.set_verbose()
    parser = argparse.ArgumentParser()
    parser.add_argument("config", metavar="FILE")
    parser.add_argument("checkpoint", type=str, default=None)
    parser.add_argument("--split", type=str, default="val", choices=["train", "val"])
    parser.add_argument("--mode", type=str, default="gt", choices=["gt", "pred"])

    # parser.add_argument("--split", type=str, default="val", choices=["train", "val"])

    parser.add_argument("--bbox-classes", nargs="+", type=int, default=None)
    parser.add_argument("--bbox-score", type=float, default=None)
    parser.add_argument("--map-score", type=float, default=0.5)
    parser.add_argument("--out-dir", type=str, default="viz")
    args, opts = parser.parse_known_args()

    configs.load(args.config, recursive=True)
    configs.update(opts)

    cfg = Config(recursive_eval(configs), filename=args.config)
    print('cfg: ', cfg)

    torch.backends.cudnn.benchmark = cfg.cudnn_benchmark
    torch.cuda.set_device(dist.local_rank())

    # build the dataloader
    # print('dataset config: ', cfg.data[args.split])
    # dataset = build_dataset(cfg.data[args.split])
    # dataflow = build_dataloader(
    #     dataset,
    #     samples_per_gpu=1,
    #     workers_per_gpu=cfg.data.workers_per_gpu,
    #     dist=True,
    #     shuffle=False,
    # )
    
    distributed = 0

    
    # dataset_train  = build_dataset(cfg.data.train)
    # dataflow = build_dataloader(
    #     dataset_train,
    #     samples_per_gpu=1,
    #     workers_per_gpu=cfg.data.workers_per_gpu,
    #     dist=distributed,
    #     shuffle=False,
    # )
    # dataflow.collate_fn = partial(collate_fn,is_return_depth=False)
    dataset = build_dataset(cfg.data[args.split])
    dataflow = build_dataloader(
        dataset,
        samples_per_gpu=1,
        workers_per_gpu=cfg.data.workers_per_gpu,
        dist=False,
        shuffle=False,
    )
    dataflow.collate_fn = partial(collate_fn,is_return_depth=False)
    
    cfg.model.train_cfg = None
    # model = build_model(cfg.model, test_cfg=cfg.get("test_cfg"))
    test_cfg = cfg['model']['heads']['object']['test_cfg']
    model = build_model(cfg.model, test_cfg=test_cfg)
    print('test_cfg:', test_cfg)
    model = model.cuda()
    
    # print('model: ', model)
    # build the model and load checkpoint
    if args.mode == "pred":
        # model = build_model(cfg.model)
        checkpoint = load_checkpoint(model, args.checkpoint, map_location="cpu")


        model = MMDataParallel(model, device_ids=[0])
        model.eval()
        # outputs = single_gpu_test(model, dataflow)
    # if args.mode == "pred":
    #     # model = build_model(cfg.model)
    #     # load_checkpoint(model, args.checkpoint, map_location="cpu")

    #     # model = MMDistributedDataParallel(
    #     #     model.cuda(),
    #     #     device_ids=[torch.cuda.current_device()],
    #     #     broadcast_buffers=False,
    #     # )
    #     model.eval()

    for data in tqdm(dataflow):
        print('data: ', data)
        print('data.keys: ', data.keys())
        print('data["metas"]: ', data["metas"])
        metas = data["metas"][0]
        # print('test: ', metas[0]['token'])

        number = metas["token"].split('/')[1].split('.')[0]
        name = "{}".format(number)

        if args.mode == "pred":
            # with torch.inference_mode():  ## if torch version below 1.9 please use no_grad instead of inference_mode
            with torch.no_grad():
                outputs = model(**data)

        if args.mode == "gt" and "gt_bboxes_3d" in data:
            bboxes = data["gt_bboxes_3d"][0]
            labels = data["gt_labels_3d"][0].numpy()

            if args.bbox_classes is not None:
                indices = np.isin(labels, args.bbox_classes)
                bboxes = LiDARInstance3DBoxes(bboxes.tensor[indices], box_dim=bboxes.box_dim)
                labels = labels[indices]
        elif args.mode == "pred" and "boxes_3d" in outputs[0]:
            bboxes = outputs[0]["boxes_3d"].tensor.numpy()
            scores = outputs[0]["scores_3d"].numpy()
            labels = outputs[0]["labels_3d"].numpy()

            if args.bbox_classes is not None:
                indices = np.isin(labels, args.bbox_classes)
                bboxes = bboxes[indices]
                scores = scores[indices]
                labels = labels[indices]

            if args.bbox_score is not None:
                indices = scores >= args.bbox_score
                bboxes = bboxes[indices]
                scores = scores[indices]
                labels = labels[indices]

            # bboxes[..., 2] -= bboxes[..., 5] / 2
            angle = bboxes[..., 6]
            # for i in range(len(angle)):
            #     ang = int(angle[i]/(2*np.pi) *360)
            #     bboxes[i] = bboxes[i].rotate_z(ang)

            bboxes = LiDARInstance3DBoxes(bboxes, box_dim=9)
            # for i in range(len(angle)):
            #     bboxes[i].rotate(angle[i], bboxes[i].tensor)
            #     # bboxes[i].flip(bev_direction="horizontal")
        else:
            bboxes = None
            labels = None

        if args.mode == "gt" and data.get("gt_masks_bev") is not None:
            masks = data["gt_masks_bev"].data[0].numpy()
            masks = masks.astype(np.bool)
        elif args.mode == "pred" and "masks_bev" in outputs[0]:
            masks = outputs[0]["masks_bev"].numpy()
            masks = masks >= args.map_score
        else:
            masks = None
        # data_root = 'data/dair-v2x-i/'
        data_root = cfg.dataset_root

        if "img" in data:
            image_path =os.path.join(data_root, metas["token"])
            print('image_path: ', image_path)
            image = mmcv.imread(image_path)
            ## dtype of tranform
            print('dtype of data[''lidar2image'']:', type(data["lidar2image"]))
            visualize_camera(
                os.path.join(args.out_dir, f"camera", f"{name}.png"),
                image,
                bboxes=bboxes,
                labels=labels,
                # transform=data["lidar2image"],
                transform=data["lidar2camera"],
                transform_intrinsic =data["camera_intrinsics"],
                classes=cfg.object_classes,
                # rotation_angle=metas["rotation_angle"],
            )
            # for k, image_path in enumerate(metas["token"]):
            #     print('k:',k)
            #     print('image_path: ', image_path)
            #     image_path = os.path.join(data_root, image_path)
            #     print('image_path: ', image_path)
            #     image = mmcv.imread(image_path)
            #     visualize_camera(
            #         os.path.join(args.out_dir, f"camera-{k}", f"{name}.png"),
            #         image,
            #         bboxes=bboxes,
            #         labels=labels,
            #         transform=metas["lidar2image"][k],
            #         classes=cfg.object_classes,
            #     )

        if "points" in data:
            # lidar = data["points"].data[0][0].numpy()
            lidar = data["points"][0].numpy()
            print('lidar:', lidar)
            visualize_lidar(
                os.path.join(args.out_dir, "lidar", f"{name}.png"),
                lidar,
                bboxes=bboxes,
                labels=labels,
                xlim=[cfg.point_cloud_range[d] for d in [0, 3]],
                ylim=[cfg.point_cloud_range[d] for d in [1, 4]],
                classes=cfg.object_classes,
            )

        if masks is not None:
            visualize_map(
                os.path.join(args.out_dir, "map", f"{name}.png"),
                masks,
                classes=cfg.map_classes,
            )        


if __name__ == "__main__":
    main()
