# How to Download and Convert RADDet Dataset

In this tutorial you will learn how to download and convert the `RADDet` dataset that can be processed by Intel® Metro AI Suite Sensor Fusion for Traffic Management.

## RADDet Dataset

### Download

Download dataset from [BaiduPan](https://pan.baidu.com/s/1kBgFDzP04MUs61NF6NTPGA?pwd=i98h)

**Attention:** 

Download the dataset and arrange it as the following directory tree:

```Shell.bash
|-- raddet_adc
	|-- ADC
		|-- ******.npy
		|-- ******.npy
|-- sensors_para
	|-- registration_matrix
		|-- registration_matrix.npy
	|-- stereo_para
		|-- left_maps.npy
		|-- ProjLeft.npy
		|-- ProjRight.npy
		|-- Q.npy
		|-- right_maps.npy
		|-- roiL.npy
		|-- roiR.npy
|-- test
	|-- RAD
		|-- part1
			|-- ******.npy
			|-- ******.npy
		|-- part2
			|-- ******.npy
			|-- ******.npy
	|-- gt
		|-- part1
			|-- ******.pickle
			|-- ******.pickle
		|-- part2
			|-- ******.pickle
			|-- ******.pickle
	|-- stereo_image
		|-- part1
			|-- ******.jpg
			|-- ******.jpg
		|-- part2
			|-- ******.jpg
			|-- ******.jpg
|-- train
	|-- RAD
		|-- part1
			|-- ******.npy
			|-- ******.npy
		|-- part2
			|-- ******.npy
			|-- ******.npy
	|-- gt
		|-- part1
			|-- ******.pickle
			|-- ******.pickle
		|-- part2
			|-- ******.pickle
			|-- ******.pickle
	|-- stereo_image
		|-- part1
			|-- ******.jpg
			|-- ******.jpg
		|-- part2
			|-- ******.jpg
			|-- ******.jpg
```

### Dataset description

The details of the data capture is shown below.

```
"designed_frequency":			76.8 Hz,
"config_frequency":			77 Hz,
"range_size":				256,
"maximum_range":			50 m,
"doppler_size":				64,
"azimuth_size":				256,
"range_resolution":			0.1953125 m/bin,
"angular_resolution":			0.006135923 radian/bin,
"velocity_resolution":			0.41968030701528203 (m/s)/bin
```

The dataset has totally **6** categories, different input formats and ground truth formats. All the information that stored in the dataset can be concluded as follow.

```
RAD:		3D-FFT radar data with size (256, 256, 64)
stereo_image:	2 rectified stereo images
gt:		ground truth with {"classes", "boxes", "cart_boxes"}
sensors_para: 	"stereo_para" for stereo depth estimation, and "registration_matrix" for cross-sensor registration
```

**Note:** for the `classes`, they are `["person", "bicycle", "car", "motorcycle", "bus", "truck" ]`.

**Also Note:** for the `boxes`, the format is `[x_center, y_center, z_center, w, h, d]`.

**Also Note:** for the `cart_box`, the format is `[x_center, y_center, w, h]`.

**Also Note:** for the `stereo_para`, `left_maps.npy` and `right_maps.npy` are derived from `cv2.initUndistortRectifyMap(...)`; all other matrices are derived from `cv2.stereoRectify(...)`.

**License**: MIT License

## Generate left image and radar data, then convert to bin file as multi sensor input

```Shell.bash
cd $PROJ_DIR/deployments/raddet_tools

python3 -m venv raddet-test

source raddet-test/bin/activate

python3 -m pip install --upgrade pip

pip install -r requirements.txt

export RADDET_DATASET_ROOT=/path/to/datasets/RADDet
# dataset org:

cd scripts
bash process_dataset.sh $RADDET_DATASET_ROOT

```

Upon success, the radar data and the corresponding left image will be extracted, the directory tree should be as follows:

```Shell.bash
|-- bin_files_v1.0
	|-- bgr
		|-- ******.bin
		|-- ******.bin
	|-- radar
		|-- ******.bin
		|-- ******.bin
|-- raddet_adc
	|-- ADC
		|-- ******.npy
		|-- ******.npy
|-- sensors_para
	|-- registration_matrix
		|-- registration_matrix.npy
		|-- registration_matrix.bin
	|-- stereo_para
		|-- left_maps.npy
		|-- left_maps.bin
		|-- ProjLeft.npy
		|-- ProjLeft.bin
		|-- ProjRight.npy
		|-- ProjRigh.bin
		|-- Q.npy
		|-- Q.bin
		|-- right_maps.npy
		|-- right_maps.bin
		|-- roiL.npy
		|-- roiL.bin
		|-- roiR.npy
		|-- roiR.bin
|-- test
	|-- RAD
		|-- part1
			|-- ******.npy
			|-- ******.npy
		|-- part2
			|-- ******.npy
			|-- ******.npy
	|-- gt
		|-- part1
			|-- ******.pickle
			|-- ******.pickle
		|-- part2
			|-- ******.pickle
			|-- ******.pickle
	|-- stereo_image
		|-- part1
			|-- ******.jpg
			|-- ******.jpg
		|-- part2
			|-- ******.jpg
			|-- ******.jpg
	|-- left
		|-- part1
			|-- ******.jpg
			|-- ******.jpg
		|-- part2
			|-- ******.jpg
			|-- ******.jpg
|-- train
	|-- RAD
		|-- part1
			|-- ******.npy
			|-- ******.npy
		|-- part2
			|-- ******.npy
			|-- ******.npy
	|-- gt
		|-- part1
			|-- ******.pickle
			|-- ******.pickle
		|-- part2
			|-- ******.pickle
			|-- ******.pickle
	|-- stereo_image
		|-- part1
			|-- ******.jpg
			|-- ******.jpg
		|-- part2
			|-- ******.jpg
			|-- ******.jpg
	|-- left
		|-- part1
			|-- ******.jpg
			|-- ******.jpg
		|-- part2
			|-- ******.jpg
			|-- ******.jpg
```

Where `bin_files_v1.0` stores all the bin files as multi sensor input.