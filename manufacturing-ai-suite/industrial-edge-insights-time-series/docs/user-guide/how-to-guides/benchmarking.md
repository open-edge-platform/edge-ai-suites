# Benchmarking

This guide explains how to run benchmarking for Docker Compose deployments in Time Series Analytics sample apps.

## Enable Benchmarking

To enable benchmarking:

1. Set `number_of_data_points_per_stream=<NUM_POINTS>` in the `make` command.
2. This enables benchmarking mode for Docker Compose by setting `ENABLE_BENCHMARKING=true`.
3. `number_of_data_points_per_stream` is forwarded to TSAM as `BENCHMARK_TOTAL_PTS` (it is not automatically multiplied by `num_of_streams`). If you want *N points per stream* with `num_of_streams` streams, pass `number_of_data_points_per_stream=<N * num_of_streams>`.

## Parameter Reference

- `num_of_streams=<NUMBER_OF_STREAMS>`: Number of parallel ingestion streams.
- `number_of_data_points_per_stream=<NUM_POINTS>`: Number of points ingested per stream.

> **Note:** If `num_of_streams` is not set, the default value is `1`.


## With Stream Processing User Defined Function (UDF)

To run benchmarking with stream processing UDF, use the following command.

For example, for Wind Turbine Anomaly Detection, use:

```bash
make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=<NUMBER_OF_STREAMS> number_of_data_points_per_stream=<NUM_POINTS>
```

Example:

```bash
make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=4 number_of_data_points_per_stream=500
```


## With Batch Processing User Defined Function (UDF)

To run benchmarking with batch processing UDF, append `batch` to the `make` command.

For example, for Wind Turbine Anomaly Detection, use:

```bash
make up_mqtt_ingestion batch app=wind-turbine-anomaly-detection num_of_streams=<NUMBER_OF_STREAMS> number_of_data_points_per_stream=<NUM_POINTS>
```

Example:

```bash
make up_mqtt_ingestion batch app=wind-turbine-anomaly-detection num_of_streams=4 number_of_data_points_per_stream=500
```

## Notes

- Ensure system resources (CPU, memory) are sufficient to support the desired number of streams.
- For troubleshooting or monitoring, use `make status` to verify container health and logs.
- For batch benchmarking, confirm your app package includes batch UDF artifacts before deployment.

    > **Note:** 
    > 1. The command `make status` may show errors in containers like ia-grafana when users have not logged in yet, 
    > or after a session timeout.
    > 2. Log in to Grafana again and, if functionality is working, ignore `user token not found` errors and other minor Grafana log errors.


  ```sh
  make status
  ```
