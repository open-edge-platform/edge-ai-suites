# How to Run Model Evaluation Tools for RADDet Dataset

In this tutorial you will learn how to run model evaluation tools for RaDDet dataset.



## Environment set-up

```shell
# Step 1: Create virtual environment
python3 -m venv evaluation_env

# Step 2: Activate virtual environment
source evaluation_env/bin/activate

# Step 3: Upgrade pip to latest version
python3 -m pip install --upgrade pip

# Step 4: Download and install the package
pip install -r requirements.txt
```



## GT prepare

Since the raddet dataset does not have GT for the image, a manual annotation is required.

##### First using yolov10x model for auto-annatation

Usage:
```bash
python raddet_annotation.py --model [selected model, default yolov10x.pt] --img_dir [input image file folder] --out_dir [output label file folder, default gt] --vis_dir [folder for visualize the image with bbox, default vis]
```
For example:

```
python raddet_annotation.py --img_dir ./images --out_dir ./gt
```

Then you will get a labeling folder, which contains the labeled txt files. The file name is the corresponding image name, and each line stores the corresponding category and detection box in `cxcywhn` format.



##### Manually correct the annotation results using labelimg

Then you can use the [labelimg](https://github.com/HumanSignal/labelImg/releases) tool to manually correct the automatic labeling results.

Use "`Open Dir`" to set the input image directory to the original image directory, and use "`Change Save Dir`" to set the gt directory just generated to the output directory. At the same time, modify the content in predefined_classes.txt to the corresponding category. `labelimg` will automatically load the automatic annotation results, and you can manually correct them based on this.



## Prediction results preparation

Usage:
```bash
Usage: testGRPCLocalPipeline_pred <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <media_type> <pred_dir> [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```
* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: ai pipeline topology file.
* **total_stream_num**: to control the input streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: multi-sensor binary files folder for input.
* **media_type**: input media type. Currently only support `multisensor`.
* **pred_dir**: Output predication files folder.
* **pipeline_repeats**: pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warmup flag before pipeline start.

For example:

```bash
sudo bash run_service_bare_log.sh
```

Then open another terminal:

```bash
sudo -E ./build/bin/testGRPCLocalPipeline_pred 127.0.0.1 50052 ./ai_inference/test/configs/raddet/1C1R/localMediaPipeline.json 1 1 /path/to/dataset multisensor /path/to/pred_folder
```

**Note: Please make sure that folder `pred_folder` exists.**


The `pred_folder` contains the predication .txt files. The file name is the corresponding image frame number, and each line stores the corresponding category, confidence and detection box in `x1y1x2y2` format.



## Run model evaluation tools

**Currently, there are only two categories in our test set: car and truck**

Usage:

```bash
python evaluation.py --gt_dir [input gt file folder] --pred_dir [input predication file folder] --thres [iou threshold, default 0.5]
```

For example:

```bash
python evaluation.py --gt_dir ./gt --pred_dir ./pred --thres 0.2
```

