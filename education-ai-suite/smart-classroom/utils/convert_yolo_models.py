from os import PathLike
from pathlib import Path
from zipfile import ZipFile
import shutil

import openvino as ov
from ultralytics import YOLO
from ultralytics.data.utils import DATASETS_DIR
from ultralytics.utils import DEFAULT_CFG
from ultralytics.cfg import get_cfg
from ultralytics.data.utils import check_det_dataset
from ultralytics.models.yolo.pose import PoseValidator
from ultralytics.utils.metrics import OKS_SIGMA
import nncf

DATA_URL = "https://ultralytics.com/assets/coco8-pose.zip"
CFG_URL = "https://raw.githubusercontent.com/ultralytics/ultralytics/v8.1.0/ultralytics/cfg/datasets/coco8-pose.yaml"

OUT_DIR = DATASETS_DIR
DATA_PATH = OUT_DIR / "val2017.zip"
CFG_PATH = OUT_DIR / "coco8-pose.yaml"


def download_file(
    url: PathLike,
    filename: PathLike = None,
    directory: PathLike = None
) -> PathLike:
    import requests
    import urllib.parse

    filename = filename or Path(urllib.parse.urlparse(url).path).name
    chunk_size = 16384  # make chunks bigger so that not too many updates are triggered for Jupyter front-end

    filename = Path(filename)
    filepath = Path(directory) / filename if directory is not None else filename
    if filepath.exists():
        return filepath.resolve()

    # create the directory if it does not exist, and add the directory to the filename
    if directory is not None:
        Path(directory).mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(
            url=url, headers={"User-agent": "Mozilla/5.0"}, stream=True
        )
        response.raise_for_status()
    except (
        requests.exceptions.HTTPError
    ) as error:  # For error associated with not-200 codes. Will output something like: "404 Client Error: Not Found for url: {url}"
        raise Exception(error) from None
    except requests.exceptions.Timeout:
        raise Exception(
            "Connection timed out. If you access the internet through a proxy server, please "
            "make sure the proxy is set in the shell from where you launched Jupyter."
        ) from None
    except requests.exceptions.RequestException as error:
        raise Exception(f"File downloading failed with error: {error}") from None

    # download the file if it does not exist
    if not filepath.exists():
        with open(filepath, "wb") as file_object:
            for chunk in response.iter_content(chunk_size):
                file_object.write(chunk)
    else:
        print(f"'{filepath}' already exists.")

    response.close()

    return filepath.resolve()


if not (OUT_DIR / "coco8-pose/labels").exists():
    download_file(DATA_URL, DATA_PATH.name, DATA_PATH.parent)
    download_file(CFG_URL, CFG_PATH.name, CFG_PATH.parent)
    with ZipFile(DATA_PATH, "r") as zip_ref:
        zip_ref.extractall(OUT_DIR)


def convert_yolo_to_openvino(model_name: str, output_dir: str):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    # Check if quantized model already exists
    int8_model_pose_path = output_path / f"{model_name}.xml"
    if int8_model_pose_path.exists() and (output_path / f"{model_name}.bin").exists():
        return

    pt_file = Path(f"{model_name}.pt")
    pose_model = YOLO(f"{model_name}.pt")
    label_map = pose_model.model.names

    pose_model_dir = output_path / f"{model_name}_openvino_model"
    pose_model_path = pose_model_dir / f"{model_name}.xml"
    if not pose_model_path.exists():
        # Export to a temporary location then move to output_dir
        temp_export_dir = Path(f"{model_name}_openvino_model")
        pose_model.export(format="openvino", dynamic=True, half=True)
        # Move the exported model to output_dir
        if temp_export_dir.exists():
            shutil.move(str(temp_export_dir), str(pose_model_dir))

    if pt_file.exists():
        pt_file.unlink()

    core = ov.Core()
    pose_ov_model = core.read_model(pose_model_path)

    args = get_cfg(cfg=DEFAULT_CFG)
    args.data = "coco8-pose.yaml"

    pose_validator = PoseValidator(args=args)
    pose_validator.data = check_det_dataset(args.data)
    pose_validator.stride = 32
    pose_data_loader = pose_validator.get_dataloader(OUT_DIR / "coco8-pose", 1)

    pose_validator.is_coco = True
    pose_validator.names = label_map
    pose_validator.metrics.names = pose_validator.names
    pose_validator.nc = 1
    pose_validator.sigma = OKS_SIGMA

    def transform_fn(data_item: dict):
        return pose_validator.preprocess(data_item)["img"].numpy()

    quantization_dataset = nncf.Dataset(pose_data_loader, transform_fn)
    ignored_scope = nncf.IgnoredScope(  # post-processing
        subgraphs=[
            nncf.Subgraph(
                inputs=[
                    f"__module.model.{22 if 'v8' in model_name else 23}/aten::cat/Concat",
                    f"__module.model.{22 if 'v8' in model_name else 23}/aten::cat/Concat_1",
                    f"__module.model.{22 if 'v8' in model_name else 23}/aten::cat/Concat_2",
                    f"__module.model.{22 if 'v8' in model_name else 23}/aten::cat/Concat_7",
                ],
                outputs=[
                    f"__module.model.{22 if 'v8' in model_name else 23}/aten::cat/Concat_9"
                ],
            )
        ]
    )

    quantized_pose_model = nncf.quantize(
        pose_ov_model,
        quantization_dataset,
        preset=nncf.QuantizationPreset.PERFORMANCE,
        ignored_scope=ignored_scope,
    )
    quantized_pose_model.reshape([1, 3, 384, 640])
    quantized_pose_model.set_rt_info("yolo_v8_pose" if 'v8' in model_name else "yolo_v11_pose", ['model_info', 'model_type'])
    quantized_pose_model.set_rt_info("sit stand sit_raise_up stand_raise_up", ['model_info', 'labels'])

    print(f"Quantized model will be saved to {int8_model_pose_path}")
    ov.save_model(quantized_pose_model, str(int8_model_pose_path))

def convert_yolo_models(output_dir: str = "models/va"):
    convert_yolo_to_openvino("yolov8s-pose", output_dir)
    convert_yolo_to_openvino("yolov8m-pose", output_dir)

if __name__ == "__main__":
    convert_yolo_models()