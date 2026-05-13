# How to Run Accuracy Benchmark for RADDet Dataset

In this tutorial you will learn how to run radar detection accuracy benchmark for RaDDet dataset.

## Environment set-up

```shell
# Step 1: Create virtual environment
python3 -m venv benchmark_env

# Step 2: Activate virtual environment
source benchmark_env/bin/activate

# Step 3: Upgrade pip to latest version
python3 -m pip install --upgrade pip

# Step 4: Download and install the package
pip install -r requirements.txt
```

## Dataset prepare

First, download raddet dataset and original adc files, and put adc data in the same folder. Arrange the dataset as the following directory tree:

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

## Create a folder to save radar tracking results and the benchmark results

Pepare offline radar tracking results and put radarResults.csv in this folder.You can get the radar tracking results with the command in [Sec 5.3.2.7. README.](../../README.md)
After running benchmark, you can get all the intermediate results for the benchark in this foler.

## Run accuracy benchmark

```Shell.bash
export DATASET_ROOT_DIR=/path/to/datasets/RADDet
export DEST_PATH=/path/to/folder

cd deployments/benchmark_tools
bash prepare_data_run_benchmark.sh $DATASET_ROOT_DIR $DEST_PATH

```