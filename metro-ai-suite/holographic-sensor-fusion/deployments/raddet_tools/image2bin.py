import os
import cv2
from glob import glob
import numpy as np
from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description="")
parser.add_argument(
    "--dataset_folder",
    required=True,
    type=str,
    help="dataset folder.",
)
parser.add_argument(
    "--save_folder",
    required=True,
    type=str,
    help="save folder.",
)

args = parser.parse_args()


def checkoutDir(dir_name: str):
    """
    Function:
        Checkout if the directory is exists, if not then create one

    Args:
        dir_name            ->          directory name
    """
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
        # os.mkdir(dir_name)
    else:
        file_list = glob(os.path.join(dir_name, "*"))
        if len(file_list) != 0:
            for f in file_list:
                os.remove(f)


def encode_img(img, flag):
    """
    img.shape: (480, 640, 3)
    img_encode.shape: (52537, 1)
    """

    # Encode, flag(True) for camera, flag(False) for depth image(png encode for 16U depth image)
    if flag:
        img_encode = cv2.imencode(".jpg", img)[1]
    else:
        img_encode = cv2.imencode(".png", img)[1]
    # # Get base64 bytes
    # base64_encode = base64.b64encode(img_encode)
    # # Get base64 string
    # base64_encode = base64_encode.decode()

    # narr = np.fromstring(base64.b64decode(str(base64_encode)), dtype=np.uint8)
    # debug = cv2.imdecode(narr, cv2.IMREAD_COLOR)
    # cv2.imwrite("/opt/hce-core/output_logs/resultsink/debug.jpg", debug)

    return img_encode


def image2bin(dataset_folder: str, save_folder: str):
    radar_save_folder = os.path.join(save_folder, "radar")
    checkoutDir(radar_save_folder)
    bgr_save_folder = os.path.join(save_folder, "bgr")
    checkoutDir(bgr_save_folder)
    # disparity_save_folder = os.path.join(save_folder, "depth")
    # checkoutDir(disparity_save_folder)

    radar_folder = os.path.join(dataset_folder, "raddet_adc/ADC")
    bgr_train_folder = os.path.join(dataset_folder, "train/left")
    # disparity_train_folder = os.path.join(dataset_folder, "train/disparity")
    bgr_test_folder = os.path.join(dataset_folder, "test/left")
    # disparity_test_folder = os.path.join(dataset_folder, "test/disparity")

    radar_files = glob(os.path.join(radar_folder, "[!._]*.npy"))
    radar_files = sorted(radar_files)
    for file_path in radar_files:
        radar = np.load(file_path)
        radar = radar.astype(np.complex64)
        radar = radar.reshape((256, 64, 8))
        raw_adc = np.zeros(radar.shape, dtype="complex64", order="C")
        # w, h, d = radar.shape
        # for c in range(d):
        #     temp = int((c%4)*2+c/4)
        #     radar[:,:,c] = radar[:,:,temp]
        dataTmp1 = radar[:, :, 0:-1:2]
        dataTmp2 = radar[:, :, 1::2]
        raw_adc[:, :, 0:4] = (dataTmp1 - dataTmp2) / 2
        raw_adc[:, :, 4:8] = (dataTmp1 + dataTmp2) / 2
        radar = raw_adc
        radar = np.flipud(radar)
        radar = radar.transpose((1, 2, 0))
        radar.tofile(os.path.join(radar_save_folder, os.path.basename(file_path).replace(".npy", ".bin")))

    items = os.listdir(bgr_train_folder)
    items = sorted(items)
    folders = []
    for item in items:
        if not os.path.isfile(os.path.join(bgr_train_folder, item)):
            folders.append(item)
    for folder in folders:
        bgr_train_folder2 = os.path.join(bgr_train_folder, folder)
        # disparity_train_folder2 = bgr_train_folder2.replace("left", "disparity")

        left_images = sorted(glob(os.path.join(bgr_train_folder2, "*.jpg")))
        for image_path in left_images:
            left_image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            left_image = encode_img(left_image, True)
            # disparity_image_path = image_path.replace("left", "disparity")
            # disparity_image_path = disparity_image_path.replace(".jpg", ".tif")
            # disparity_image = cv2.imread(disparity_image_path, cv2.IMREAD_UNCHANGED)

            left_image.tofile(os.path.join(bgr_save_folder, os.path.basename(image_path).replace(".jpg", ".bin")))
            # disparity_image.tofile(
            #     os.path.join(disparity_save_folder, os.path.basename(image_path).replace(".jpg", ".bin"))
            # )

    items = os.listdir(bgr_test_folder)
    items = sorted(items)
    folders = []
    for item in items:
        if not os.path.isfile(os.path.join(bgr_test_folder, item)):
            folders.append(item)
    for folder in folders:
        bgr_test_folder2 = os.path.join(bgr_test_folder, folder)

        left_images = sorted(glob(os.path.join(bgr_test_folder2, "*.jpg")))
        for image_path in left_images:
            left_image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            left_image = encode_img(left_image, True)
            # disparity_image_path = image_path.replace("left", "disparity")
            # disparity_image_path = disparity_image_path.replace(".jpg", ".tif")
            # disparity_image = cv2.imread(disparity_image_path, cv2.IMREAD_UNCHANGED)

            left_image.tofile(os.path.join(bgr_save_folder, os.path.basename(image_path).replace(".jpg", ".bin")))
            # disparity_image.tofile(
            #     os.path.join(disparity_save_folder, os.path.basename(image_path).replace(".jpg", ".bin"))
            # )


if __name__ == "__main__":
    image2bin(args.dataset_folder, args.save_folder)
