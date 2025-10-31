# How to use CPU for inference

## CPU specific element properties

DL Streamer inference elements also provides property such as `device=CPU` and `pre-process-backend=opencv` to infer and pre-process on CPU. Read DL Streamer [docs](https://dlstreamer.github.io/dev_guide/model_preparation.html#model-pre-and-post-processing) for more.

## Tutorial on how to use CPU specific pipelines

The pipeline `object_tracking_cpu` in [pipeline-server-config](../../src/dlstreamer-pipeline-server/config.json) contains CPU specific elements and uses CPU backend for inferencing. We can start the pipeline as follows:

```sh
./sample_start.sh cpu
```

Go to grafana as explained in [get-started](./get-started.md) to view the dashboard.