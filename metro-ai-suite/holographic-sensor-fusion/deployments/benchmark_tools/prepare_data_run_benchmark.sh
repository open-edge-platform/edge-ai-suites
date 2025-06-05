#!/bin/bash

## prepare raddet dataset
## download raddet dataset and original adc files, put adc data in the same folder
## prepare offline radar tracking results and put radarResults.csv in the same folder

DATASET_ROOT_DIR=${1-~/datasets/RADDet}
train_path=$DATASET_ROOT_DIR/train
test_path=$DATASET_ROOT_DIR/test

ori_adc_path=$DATASET_ROOT_DIR/ADC

# prepare gt, rad and stereo image
# 1.0 select data snippet eg: filenumber: [559, 724]

# prepare destination directory

DEST_PATH=${2-~/datasets/raddet}
mkdir $DEST_PATH

python3 select_raddet_data.py --dataset_folder $train_path --save_folder $DEST_PATH
python3 select_raddet_data.py --dataset_folder $test_path --save_folder $DEST_PATH


# select matched image and adc
dest_image_path=$DEST_PATH/stereo_image

echo "dest_image_path"
echo $dest_image_path


dest_adc_path=$DEST_PATH/adc
mkdir $dest_adc_path

files=$(ls $dest_image_path)
for filename in $files
do 
#   echo $filename
  echo ${filename%.*}
  file_name=${filename%.*}
  new_adc_file_name=$ori_adc_path/$file_name.npy

  echo $new_adc_file_name

  cp $new_adc_file_name $dest_adc_path

done

## split stereo_images into left and right
python3 split_images.py --folder_path $DEST_PATH

## read gt information and create radar gt csv file
python3 read_GT_plot_multiple.py --folder_path $DEST_PATH

## read offline radar tracking results and plot
python3 read_tracking_results_plot_multiple.py --folder_path $DEST_PATH

## caculate accuacy with radar detection results and gt
python3 accuracy_benchmark.py --folder_path $DEST_PATH




