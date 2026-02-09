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
   
    > **NOTE:** 
    > Use `kubectl exec -it <influxdb-pod-name> -n <namespace> -- /bin/bash` for the helm deployment
    > where for <namespace> replace with namespace name where the application was deployed and
    > for <influxdb-pod-name> replace with InfluxDB pod name.

2. Query the vision metadata:

    ```bash
    # For below command, the INFLUXDB_USERNAME and INFLUXDB_PASSWORD needs to be fetched from `.env` file
    influx -username <username> -password <password>
    USE datain
    SHOW MEASUREMENTS

    # View vision detection results
    SELECT * FROM "vision-weld-classification-results"
    ```

> **NOTE:** You may see the error `There was an error writing history file: open /.influx_history: read-only file system` in the InfluxDB shell. This is harmless and does not affect functionality.

## Accessing Stored Images using SeaweedFS Filer Web Interface

Access the SeaweedFS Filer interface in your web browser:

```
https://<host_ip>:3000/image-store/buckets/dlstreamer-pipeline-results/weld-defect-classification/
```

> **Note:** Use link `https://<host_ip>:30001/image-store/buckets/dlstreamer-pipeline-results/weld-defect-classification/` to access the SeaweedFS Filer interface for the Helm deployment.

Images are organized by their `img_handle` identifier. Browse the directory to locate specific images, then click to view the image.

## Mapping Vision Metadata to Stored Images

Follow these steps to correlate detection events in InfluxDB with stored images:

1. Query InfluxDB to retrieve vision metadata:
   ```sql
   SELECT * FROM "vision-weld-classification-results"
   ```

2. Note the `img_handle` from the query results (e.g., `X7TINNVPNX`).

3. Navigate to the Filer interface:
   ```
   http://<host_ip>:8887/buckets/dlstreamer-pipeline-results/weld-defect-classification/
   ```

4. Locate and open the file matching the `img_handle` (e.g., `X7TINNVPNX.jpg`).
