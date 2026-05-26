# Benchmarking

This guide explains how to run benchmarking for Docker Compose deployments in Time Series Analytics sample apps.

## Enable Benchmarking

To enable benchmarking:

1. Set `number_of_data_points_per_stream=<NUM_POINTS>` in the `make` command.
2. This automatically enables benchmarking mode for Docker Compose by setting `ENABLE_BENCHMARKING=true`.
3. The total point count passed to the Time Series Analytics Microservice (TSAM) service is derived from stream count:

   `BENCHMARK_TOTAL_PTS = number_of_data_points_per_stream * num_of_streams`

## Parameter Reference

- `num_of_streams=<NUMBER_OF_STREAMS>`: Number of parallel ingestion streams.
- `number_of_data_points_per_stream=<NUM_POINTS>`: Number of points ingested per stream.

> **Note:** If `num_of_streams` is not set, the default value is `1`.


## With Stream Processing User Defined Function (UDF)

To run benchmarking with stream processing UDF, use the following command.

For example, for Weld Defect Detection, use:

```bash
make up_mqtt_ingestion app=weld-defect-detection num_of_streams=<NUMBER_OF_STREAMS> number_of_data_points_per_stream=<NUM_POINTS>
```

Example:

```bash
make up_mqtt_ingestion app=weld-defect-detection num_of_streams=4 number_of_data_points_per_stream=500
```


## With Batch Processing User Defined Function (UDF)

To run benchmarking with batch processing UDF, append `batch` to the `make` command.

For example, for Weld Defect Detection, use:

```bash
make up_mqtt_ingestion batch app=weld-defect-detection num_of_streams=<NUMBER_OF_STREAMS> number_of_data_points_per_stream=<NUM_POINTS>
```

Example:

```bash
make up_mqtt_ingestion batch app=weld-defect-detection num_of_streams=4 number_of_data_points_per_stream=500
```

## Notes

- Ensure system resources (CPU, memory) are sufficient to support the desired number of streams.
- For troubleshooting or monitoring, use `make status` to verify container health and logs.
- For batch benchmarking, confirm your app package includes batch UDF artifacts before deployment.

  > **Note:** The command `make status` may show errors in containers like ia-grafana when users have not logged in
  > for the first login or due to session timeout. Log in to Grafana again and, if functionality is working,
  > ignore `user token not found` errors and other minor Grafana log errors.

  ```sh
  make status
  ```
