import os
import cv2
from glob import glob
import numpy as np
from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description="")
parser.add_argument(
    "--stereo_image_folder",
    required=True,
    type=str,
    help="stereo image folder.",
)
parser.add_argument(
    "--sensors_para_folder",
    required=True,
    type=str,
    help="sensors parameter folder.",
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


class Config(object):
    def __init__(self, sensors_para_folder: str) -> None:
        sensors_para_folder = Path(sensors_para_folder)
        registration_matrix_folder = sensors_para_folder.joinpath("registration_matrix")
        stereo_para_folder = sensors_para_folder.joinpath("stereo_para")

        self.registration_matrix = np.load(registration_matrix_folder.joinpath("registration_matrix.npy"))
        self.left_maps = np.load(stereo_para_folder.joinpath("left_maps.npy"))
        self.right_maps = np.load(stereo_para_folder.joinpath("right_maps.npy"))
        self.proj_left = np.load(stereo_para_folder.joinpath("ProjLeft.npy"))
        self.proj_right = np.load(stereo_para_folder.joinpath("ProjRight.npy"))
        self.roi_l = tuple(map(int, np.load(stereo_para_folder.joinpath("roiL.npy"))))
        self.roi_r = tuple(map(int, np.load(stereo_para_folder.joinpath("roiR.npy"))))
        self.q = np.load(stereo_para_folder.joinpath("Q.npy"))

        self.save_disparity = True


def SBGMBuildDisparity(Left_Remap, Right_Remap):
    """
    Functionality:
        Build the disparity using Semi-Global Block Matching

    Inputs:
        left_maps                           ->          calibration and rectification remap parameter of left images
        right_maps                          ->          calibration and rectification remap parameter of right images

    Outputs:
        disparity                           ->          disparity maps
    """
    win_size = 7
    min_disp = 0
    # num_disp = 16*10 # Needs to be divisible by 16
    num_disp = 64  # Needs to be divisible by 16

    # other modes: MODE_SGBM, MODE_HH, MODE_SGBM_3WAY, MODE_HH4, where MODE_HH is
    # for the image size (640, 480). and also some HD pics
    left_matcher = cv2.StereoSGBM_create(
        minDisparity=min_disp,
        numDisparities=num_disp,
        blockSize=win_size,
        uniquenessRatio=10,
        speckleWindowSize=150,
        speckleRange=1,
        disp12MaxDiff=0,
        P1=8 * 3 * win_size**2,  # 8*3*win_size**2,
        P2=32 * 3 * win_size**2,
        preFilterCap=0,
        # mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY) #32*3*win_size**2)
        mode=cv2.STEREO_SGBM_MODE_HH,
    )

    right_matcher = cv2.ximgproc.createRightMatcher(left_matcher)
    lmbda = 8000
    sigma = 1.2
    visual_multiplier = 1.0

    wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=left_matcher)
    wls_filter.setLambda(lmbda)
    wls_filter.setSigmaColor(sigma)

    ############ left_matcher is the traditional matcher (default) #############
    disparity_left = left_matcher.compute(Left_Remap, Right_Remap)
    disparity_right = right_matcher.compute(Right_Remap, Left_Remap)

    filtered_img = wls_filter.filter(disparity_left, Left_Remap, None, disparity_right).astype(np.float32) / 16.0

    # filtered_img = disparity_left.astype(np.float32) / 16.0

    return filtered_img


def DisparityNormalization(disparity_map):
    """
    Function:
        normalize the disparity map for visualizaton.
    """
    disparity_map = np.int16(disparity_map * 16)
    disparity_map = cv2.normalize(src=disparity_map, dst=disparity_map, beta=0, alpha=255, norm_type=cv2.NORM_MINMAX)
    disparity_map = np.uint8(disparity_map)
    return disparity_map


def DisparityBuilding(image_path: str, config: Config):
    """
    Functionality:
        Using StereoBM and StereoSGBM for building disparity map with sepecific frames.
    """

    disparity_image = image_path.replace("stereo_image", "disparity")
    disparity_image = disparity_image.replace(".jpg", ".tif")

    img_num = int(image_path[-10:-4])
    # define a display size, for avoiding over-sized
    display_shape = (640, 480)

    # read left and right images
    image = cv2.imread(image_path)
    image_left = image[0 : config.roi_l[3], 0 : config.roi_l[2]]
    image_right = image[0 : config.roi_r[3], config.roi_l[2] : config.roi_l[2] + config.roi_r[2]]

    # using the parameters to undistort and rectify the images (transfer to gray for better disparity)
    left_rect = cv2.remap(image_left, config.left_maps[0], config.left_maps[1], cv2.INTER_LINEAR)
    left_rect_gray = cv2.cvtColor(left_rect.copy(), cv2.COLOR_BGR2GRAY)
    right_rect = cv2.remap(image_right, config.right_maps[0], config.right_maps[1], cv2.INTER_LINEAR)
    right_rect_gray = cv2.cvtColor(right_rect.copy(), cv2.COLOR_BGR2GRAY)

    # disparity of BM
    # disparity_map_sec = BMBuildDisparity(left_rect_gray, right_rect_gray, roiL, roiR)
    # disparity of SGBM
    disparity_map = SBGMBuildDisparity(left_rect, right_rect)

    return disparity_map, left_rect


def convert2bin(sensors_para_folder: str):
    config = Config(sensors_para_folder)
    registration_matrix_folder = os.path.join(sensors_para_folder, "registration_matrix")
    stereo_para_folder = os.path.join(sensors_para_folder, "stereo_para")

    registration_matrix = config.registration_matrix.astype(np.float32)
    left_maps = config.left_maps.astype(np.float32)
    right_maps = config.left_maps.astype(np.float32)
    proj_left = config.proj_left.astype(np.float32)
    proj_right = config.proj_right.astype(np.float32)
    roi_l = np.array(config.roi_l).astype(np.int32)
    roi_r = np.array(config.roi_r).astype(np.int32)
    q = config.q.astype(np.float32)

    registration_matrix.tofile(os.path.join(registration_matrix_folder, "registration_matrix.bin"))

    left_maps.tofile(os.path.join(stereo_para_folder, "left_maps.bin"))
    right_maps.tofile(os.path.join(stereo_para_folder, "right_maps.bin"))
    proj_left.tofile(os.path.join(stereo_para_folder, "ProjLeft.bin"))
    proj_right.tofile(os.path.join(stereo_para_folder, "ProjRight.bin"))
    roi_l.tofile(os.path.join(stereo_para_folder, "roiL.bin"))
    roi_r.tofile(os.path.join(stereo_para_folder, "roiR.bin"))
    q.tofile(os.path.join(stereo_para_folder, "Q.bin"))


def stereo_reconstruct(stereo_image_folder: str, sensors_para_folder: str):
    config = Config(sensors_para_folder)
    items = os.listdir(stereo_image_folder)
    items = sorted(items)
    folders = []
    for item in items:
        if not os.path.isfile(os.path.join(stereo_image_folder, item)):
            folders.append(item)

    for folder in folders:
        stereo_image_folder2 = Path(stereo_image_folder).joinpath(folder)
        # disparity_image_folder = str(stereo_image_folder2).replace("stereo_image", "disparity")
        # checkoutDir(disparity_image_folder)

        left_image_folder = str(stereo_image_folder2).replace("stereo_image", "left")
        checkoutDir(left_image_folder)

        stereo_images = sorted(list(Path(stereo_image_folder2).glob("*.jpg")))
        for image_path in stereo_images:
            # disparity_map, left_rect = DisparityBuilding(str(image_path), config)

            # read left and right images
            image = cv2.imread(image_path)
            image_left = image[0 : config.roi_l[3], 0 : config.roi_l[2]]
            # using the parameters to undistort and rectify the images (transfer to gray for better disparity)
            left_rect = cv2.remap(image_left, config.left_maps[0], config.left_maps[1], cv2.INTER_LINEAR)

            # disparity_image_path = str(image_path).replace("stereo_image", "disparity")
            # disparity_image_path = disparity_image_path.replace(".jpg", ".tif")
            # cv2.imwrite(disparity_image_path, disparity_map)

            left_image_path = str(image_path).replace("stereo_image", "left")
            cv2.imwrite(left_image_path, left_rect)


if __name__ == "__main__":
    stereo_reconstruct(args.stereo_image_folder, args.sensors_para_folder)
    convert2bin(args.sensors_para_folder)
