# Access S3 Stored Images

The DL Streamer Pipeline Server stores processed images in the SeaweedFS S3 bucket. This guide explains how to access and verify these stored images.

## Overview

All images processed by the DL Streamer Pipeline Server are stored in the S3 bucket named `dlstreamer-pipeline-results`. The images are stored in the `weld-defect-classification/` directory and named using their unique `img_handle` identifier.

## Viewing Vision Metadata in InfluxDB

The DL Streamer Pipeline Server generates vision metadata for each processed frame. This metadata is stored in InfluxDB.

### Accessing Vision Metadata

1. Connect to InfluxDB container:

    ```bash
    docker exec -it ia-influxdb bash
    ```

    > [!NOTE]
    > Use `kubectl exec -it <influxdb-pod-name> -n <namespace> -- /bin/bash` for the helm deployment
    > where for `<namespace>` replace with namespace name where the application was deployed and
    > for `<influxdb-pod-name>` replace with InfluxDB pod name.

2. Query the vision metadata:

    ```bash
    # For below command, the INFLUXDB_USERNAME and INFLUXDB_PASSWORD needs to be fetched from `.env` file
    influx -username <username> -password <password>
    USE datain
    SHOW MEASUREMENTS

    # View vision detection results
    SELECT * FROM "vision-weld-classification-results"
    ```

> [!NOTE]
> You may see the error `There was an error writing history file: open /.influx_history: read-only file system` in the InfluxDB shell. This is harmless and does not affect functionality.

## Accessing Stored Images

SeaweedFS filer endpoints are protected by SeaweedFS JWT authentication. As a result, the filer web
interface is no longer available for anonymous browser access through the sample app ingress paths.

Use an S3-compatible client with the `S3_STORAGE_USERNAME` and `S3_STORAGE_PASSWORD` credentials
from `.env` or `values.yaml` to access stored images through the authenticated `seaweedfs-s3`
gateway instead.

- **Docker Compose:** connect from a container on `timeseries_network` to `http://seaweedfs-s3:8333`.
- **Helm:** connect in-cluster to `http://seaweedfs-s3:8333`, or use
  `kubectl port-forward svc/seaweedfs-s3 8333:8333 -n <namespace>` and point your S3 client to
  `http://127.0.0.1:8333`.

## Mapping Vision Metadata to Stored Images

Follow these steps to correlate detection events in InfluxDB with stored images:

1. Query InfluxDB to retrieve vision metadata:

   ```sql
   SELECT * FROM "vision-weld-classification-results"
   ```

2. Note the `img_handle` from the query results (e.g., `X7TINNVPNX`).

3. Use an authenticated S3 client to fetch the file matching the `img_handle`
   (for example, `X7TINNVPNX.jpg`) from the `dlstreamer-pipeline-results` bucket.

> [!NOTE]
> All data stored in SeaweedFS and InfluxDB is non-persistent and will be lost on container/pod restart.
