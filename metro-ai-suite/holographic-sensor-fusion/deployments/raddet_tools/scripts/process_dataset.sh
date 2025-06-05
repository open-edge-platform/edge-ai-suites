#!/bin/bash
DATASET_ROOT_DIR=${1-~/datasets/RADDet}
TRAIN_STEREO_IMAGE_DIR=$DATASET_ROOT_DIR/train/stereo_image
TEST_STEREO_IMAGE_DIR=$DATASET_ROOT_DIR/test/stereo_image
SENSORS_PARA_FOLDER=$DATASET_ROOT_DIR/sensors_para

python ../generate_disparity.py --stereo_image_folder $TRAIN_STEREO_IMAGE_DIR --sensors_para_folder $SENSORS_PARA_FOLDER
python ../generate_disparity.py --stereo_image_folder $TEST_STEREO_IMAGE_DIR --sensors_para_folder $SENSORS_PARA_FOLDER

python ../image2bin.py --dataset_folder $DATASET_ROOT_DIR --save_folder $DATASET_ROOT_DIR/bin_files_v1.0

python ../select_raddet.py --dataset_folder $DATASET_ROOT_DIR/bin_files_v1.0 --save_folder $DATASET_ROOT_DIR/bin_files_v1.0_select
