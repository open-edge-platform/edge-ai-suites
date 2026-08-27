from pathlib import Path
import urllib.request
import urllib.error
import http.client
import socket
import time
import torch
import torch.nn as nn
import torchvision.models as models
from torchvision import datasets
from torchvision import transforms
import openvino as ov
import nncf
import yaml
import os
import tarfile
import ssl
import certifi


# Model URLs
RESNET18 = "https://download.pytorch.org/models/resnet18-f37072fd.pth"
RESNET50 = "https://download.pytorch.org/models/resnet50-11ad3fa6.pth"
MOBILENETV2 = "https://download.pytorch.org/models/mobilenet_v2-7ebf99e0.pth"
REID_XML = "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-reidentification-retail-0288/FP16/person-reidentification-retail-0288.xml"
REID_BIN = "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-reidentification-retail-0288/FP16/person-reidentification-retail-0288.bin"

METADATA_URL = "https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/models/public/resnet-18-pytorch/model.yml"
DATASET_URL = "https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-320.tgz"
DATASET_CLASSES = 10

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

CHUNK_SIZE = 1024 * 1024
DOWNLOAD_TIMEOUT = 60
DOWNLOAD_RETRIES = 8

# Errors that mean "the transfer broke, but retrying/resuming may work".
TRANSIENT_ERRORS = (
    http.client.IncompleteRead,
    http.client.HTTPException,
    urllib.error.URLError,
    ConnectionError,
    socket.timeout,
    TimeoutError,
    ssl.SSLError,
)


def download(url, filename, output_dir):
    """Download a file if not already present, resuming interrupted transfers."""
    filepath = output_dir / filename

    if filepath.exists():
        return filepath

    print(f"Downloading {filename}...")
    _download_resumable(url, filepath)

    return filepath


def _download_resumable(url, filepath):
    """Stream `url` into `filepath`, retrying with HTTP range resume on failure.

    Write to a `.part` file in chunks so a broken connection only costs the
    remaining bytes, and only publish the final file once the expected number
    of bytes has actually arrived.
    """
    part_path = filepath.with_suffix(filepath.suffix + ".part")
    last_error = None

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        downloaded = part_path.stat().st_size if part_path.exists() else 0

        request = urllib.request.Request(url)
        if downloaded:
            request.add_header("Range", f"bytes={downloaded}-")

        try:
            with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=DOWNLOAD_TIMEOUT) as response:
                # Server ignored the range request, so start over from zero.
                resuming = response.status == 206
                if downloaded and not resuming:
                    downloaded = 0

                remaining = response.headers.get("Content-Length")
                total = downloaded + int(remaining) if remaining is not None else None

                with open(part_path, "ab" if downloaded else "wb") as f:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            print(f"\r  {downloaded * 100 // total}% "
                                  f"({downloaded / 1048576:.1f}/{total / 1048576:.1f} MB)", end="")

            if total:
                print()

            if total is not None and downloaded < total:
                raise http.client.IncompleteRead(b"", total - downloaded)

            os.replace(part_path, filepath)
            return filepath

        except TRANSIENT_ERRORS as e:
            last_error = e
            if attempt == DOWNLOAD_RETRIES:
                break
            backoff = min(2 ** attempt, 30)
            print(f"\n  Download interrupted ({type(e).__name__}: {e}); "
                  f"retrying in {backoff}s [attempt {attempt + 1}/{DOWNLOAD_RETRIES}]...")
            time.sleep(backoff)

    raise RuntimeError(f"Failed to download {url} after {DOWNLOAD_RETRIES} attempts: {last_error}") from last_error

def download_labels():
    """Extract labels from model metadata."""
    with urllib.request.urlopen(METADATA_URL) as response:
        yaml_content = response.read().decode('utf-8')
        metadata = yaml.safe_load(yaml_content)
        if metadata and 'model_info' in metadata and 'labels' in metadata['model_info']:
            labels = metadata['model_info']['labels']
            return labels
    return None

def is_within_directory(directory, target):
    directory = os.path.abspath(directory)
    target = os.path.abspath(target)
    return os.path.commonpath([directory]) == os.path.commonpath([directory, target])

def safe_extract(tar: tarfile.TarFile, path: str):
    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not is_within_directory(path, member_path):
            raise Exception(f"Unsafe tar path detected: {member.name}")

        # ✅ extract ONE member at a time
        tar.extract(member, path=path)


def download_dataset(url, dataset_path):
    archive_path = dataset_path / "imagenette2-320.tgz"

    if not (dataset_path / "imagenette2-320/val").exists():
        print(f"Downloading dataset from {url}...")
        _download_resumable(url, archive_path)

        try:
            with tarfile.open(archive_path, "r:*") as tar:
                safe_extract(tar, dataset_path)
        except tarfile.ReadError as e:
            # A corrupt archive can never extract; drop it so the next run refetches.
            os.remove(archive_path)
            raise RuntimeError(f"Dataset archive from {url} is corrupt, please re-run: {e}") from e

        os.remove(archive_path)

    return dataset_path

def convert_to_openvino(model, model_name, output_dir, input_shape=(1, 3, 224, 224)):
    """Convert PyTorch model to OpenVINO format."""
    print(f"Converting {model_name} model...")

    model.eval()
    dummy_input = torch.randn(input_shape)

    ov_model = ov.convert_model(model, example_input=dummy_input)
    ov_model.reshape({ov_model.inputs[0].get_any_name(): input_shape})

    print(f"Quantizing {model_name} model...")
    dataset_path = output_dir / "datasets"
    dataset_path.mkdir(exist_ok=True)
    dataset_path = download_dataset(DATASET_URL, dataset_path)
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    val_dataset = datasets.ImageFolder(
        root=dataset_path / "imagenette2-320/val",
        transform=transforms.Compose(
            [
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                normalize,
            ]
        ),
    )
    val_data_loader = torch.utils.data.DataLoader(val_dataset, batch_size=1, shuffle=False)

    def transform_fn(data_item):
        images, _ = data_item
        return images

    calibration_dataset = nncf.Dataset(val_data_loader, transform_fn)
    ov_quantized_model = nncf.quantize(ov_model, calibration_dataset, preset=nncf.QuantizationPreset.PERFORMANCE, advanced_parameters=nncf.AdvancedQuantizationParameters())

    ppp = ov.preprocess.PrePostProcessor(ov_quantized_model)
    ppp.input().tensor().set_layout("NCHW")
    ppp.input().preprocess().reverse_channels().scale([255.,255.,255.]).mean([0.485, 0.456, 0.406]).scale([0.229, 0.224, 0.225])
    ov_quantized_model = ppp.build()

    # Add model metadata using set_rt_info
    ov_quantized_model.set_rt_info("label", ['model_info', 'model_type'])
    labels_str = " ".join(download_labels())
    ov_quantized_model.set_rt_info(labels_str, ['model_info', 'labels'])

    # Save the quantized model
    output_path = output_dir / f"{model_name}.xml"
    ov.save_model(ov_quantized_model, output_path)
    print(f"Saved quantized OpenVINO model to {output_path}")

def add_softmax(model):
    return nn.Sequential(model, nn.Softmax(dim=1))

def convert_classification_models(output_dir: str = "models/va"):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    # Check if all required models are present
    required_models = [
        "resnet18.xml",
        "resnet18.bin",
        "resnet50.xml",
        "resnet50.bin",
        "mobilenetv2.xml",
        "mobilenetv2.bin",
        "person-reidentification-retail-0288.xml",
        "person-reidentification-retail-0288.bin"
    ]

    all_models_present = all((output_path / model).exists() for model in required_models)

    if all_models_present:
        return

    print("Processing ResNet-18")
    weights_path = download(RESNET18, "resnet18-f37072fd.pth", output_path)
    model = models.resnet18()
    model.load_state_dict(torch.load(weights_path, map_location='cpu', weights_only=False))
    model = add_softmax(model)
    convert_to_openvino(model, "resnet18", output_path, input_shape=(1, 3, 224, 224))

    print("\nProcessing ResNet-50")
    weights_path = download(RESNET50, "resnet50-19c8e357.pth", output_path)
    model = models.resnet50()
    model.load_state_dict(torch.load(weights_path, map_location='cpu', weights_only=False))
    model = add_softmax(model)
    convert_to_openvino(model, "resnet50", output_path, input_shape=(1, 3, 224, 224))
    
    print("\nProcessing MobileNetV2")
    weights_path = download(MOBILENETV2, "mobilenet_v2-b0353104.pth", output_path)
    model = models.mobilenet_v2()
    model.load_state_dict(torch.load(weights_path, map_location='cpu', weights_only=False))
    model = add_softmax(model)
    convert_to_openvino(model, "mobilenetv2", output_path, input_shape=(1, 3, 224, 224))

    print("\nProcessing person-reidentification-retail-0288")
    download(REID_XML, "person-reidentification-retail-0288-original.xml", output_path)
    download(REID_BIN, "person-reidentification-retail-0288-original.bin", output_path)
    core = ov.Core()
    reid_model = core.read_model(str(output_path / "person-reidentification-retail-0288-original.xml"))
    reid_model.set_rt_info("raw_data_copy", ['model_info', 'model_type'])
    ov.save_model(reid_model, str(output_path / "person-reidentification-retail-0288.xml"))

    print("Conversion completed!")


if __name__ == "__main__":
    convert_classification_models()
