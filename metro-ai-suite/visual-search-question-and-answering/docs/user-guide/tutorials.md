# Tutorials

These tutorials demonstrate how to use the Visual Search and QA reference implementation.

- Use your own dataset for searching
- Filtered search
- Configurable parameters

## Tutorial 1: Use your own dataset for searching

In this tutorial, you will learn how to use your own dataset for searching.

**Learning objectives**:

- By the end of this tutorial, you will be able to ingest your own dataset to vector DB and conduct search and QA based on them.

### Step 1: Put the dataset under designated host directory

1. Check `env.sh` which is sourced before executing `docker compose`, find `HOST_DATA_PATH`, which should be pre-created according to [Get Started](./get-started.md).

   ``` bash
   export HOST_DATA_PATH="$HOME/data"
   ```

2. Put your dataset (including images and videos) under this directory

### Step 2: ingest the dataset to vector DB

1. Deploy the application

2. Go to the web UI, fill in `file directory on host` with the absolute path to your dataset directory, and click `UpdateDB`

**Summary**:

In this tutorial, you learned how to use your own dataset for searching.

## Tutorial 2: Filtered search

In this tutorial, you will learn how to ingest data along with metadata to support filtered search

**Learning objectives**:

- By the end of this tutorial, you will be able to ingest data with metadata by providing matched metadata json file for each media data file in the `file directory on host` used for updating DB
- By the end of this tutorial, you will be able to manually ingest single data file with specified metadata using dataprep microservice API

- By the end of this tutorial, you will be able to conduct filtered search on web UI

### Step 1: Prepare metadata json file

1. When processing data files in `file directory on host` (for simplicity, noted as `<host_data_path>` in the following steps), the dataprep microservice automatically looks for a json file in `<host_data_path>/meta` with the same basename with the file that is being processing. For example, when processing file ``<host_data_path>/image123.png`, it looks for a `<host_data_path>/meta/image123.json`. If found, the fields in the json file would be recorded into the vector DB along with the media file as its metadata.

2. In the web UI, two example fields are supported: `camera` and `capture_date`. An example json is like:

   ```bash
   {
       "camera": "camera_1",
       "capture_date": 20250101
   }
   ```

   > **Note**
   >
   > `timestamp` is reserved by the dataprep metadata contract (it holds the frame
   > time within a video, in seconds), so the capture date uses the distinct name
   > `capture_date`. A sidecar key that collides with a reserved field is rejected
   > with an error instead of being silently dropped. The field names the UI
   > filters on can be changed with the `METADATA_CAMERA_FIELD` and
   > `METADATA_DATE_FIELD` environment variables.

3. Here is an example python function to generate fake metadata json files given the file directory

   ```python
   def generate_fake_meta(file_dir):
       if not os.path.isdir(file_dir):
           raise ValueError(f"The provided path '{file_dir}' is not a valid directory.")

       timestamp = datetime.date(2025, 1, 1)
       timestamp = int(timestamp.strftime("%Y%m%d"))  # 20250101

       cnt = 1
       month = 1

       meta_dir = os.path.join(file_dir, "meta")
       os.makedirs(meta_dir, exist_ok=True)

       for root, _, files in os.walk(file_dir):
           if root.split("/")[-1] == "meta":
               continue
           for file_name in files:
               file_path = os.path.join(root, file_name)
               # Skip directories, only process files
               if os.path.isfile(file_path):
                   # Generate the JSON file name
                   base_name, _ = os.path.splitext(file_name)
                   json_file_path = os.path.join(meta_dir, f"{base_name}.json")
                   fake_label = f"camera_{cnt}"
                   timestamp = datetime.date(2025, month, cnt % 30 + 1)  # Increment day, reset to 1 if exceeds 30
                   fake_capture_date = int(timestamp.strftime("%Y%m%d"))
                   fake_meta = {
                       "camera": fake_label,
                       "capture_date": fake_capture_date
                   }
                   cnt += 1
                   if cnt > month*30:
                       month += 1
                   # Write the JSON content to the file
                   with open(json_file_path, "w") as json_file:
                       json.dump(fake_meta, json_file, indent=4)
   ```

4. Also, you may call the dataprep microservice API directly to ingest a
   directory with metadata that applies to every file in it. Per-file sidecars
   take precedence over this request-level metadata:

    ```bash
    # ingest <host_data_path>/<sub_dir> with shared metadata
    curl -X POST "http://${host_ip}:${DATAPREP_SERVICE_PORT}/v1/dataprep/media/ingest-dir" \
    -H "Content-Type: application/json" \
    -d '{
        "dir_path": "<sub_dir>",
        "bucket_name": "vsqa",
        "store_copy": false,
        "metadata": {"camera": "camera_7"}
    }'

    # the response returns a job_id; poll it until it reaches a terminal state
    curl "http://${host_ip}:${DATAPREP_SERVICE_PORT}/v1/dataprep/media/jobs/<job_id>"

    # remove everything ingested into the bucket
    curl -X DELETE "http://${host_ip}:${DATAPREP_SERVICE_PORT}/v1/dataprep/media/vsqa"
    ```

   `dir_path` is resolved under the directory the service has mounted as its
   ingest root (the same `HOST_DATA_PATH` the UI uses), and `store_copy: false`
   embeds the files in place instead of duplicating them into the service's
   storage.

   > **Note on how results are displayed:** the UI renders each search hit
   > straight from the dataprep streaming endpoint
   > (`GET /v1/dataprep/media/download`), which advertises `Accept-Ranges: bytes`
   > and answers `Range` requests with `206 Partial Content`. The browser
   > therefore seeks within a video without the application ever loading the
   > whole file. That URL is built from `DATAPREP_PUBLIC_BASE_URL`, so it must be
   > reachable **from the browser**; it defaults to
   > `http://${host_ip}:${DATAPREP_SERVICE_PORT}` in the compose deployments.
   > Set it explicitly when the browser reaches dataprep through a different
   > address (for example an ingress or NodePort in Kubernetes).

### Step 2: Use metadata as filter on web UI

Once the metadata is available, it can be used for filtered search

![Search without filter](./_assets/filter_before.png)\
*Figure 1: Search without filter*

![Search with filter](./_assets/filter_after.png)\
*Figure 2: Search with filter*

### Supported filters

**Summary**:

In this tutorial, you learned how to: ingest data with metadata (both via providing a json file or via API), and search with filters enabled

## Tutorial 3: Configurable parameters

In this tutorial, you will learn how to adjust the configuarable parameters for the application

**Learning objectives**:

- By the end of this tutorial, you will be able to know which parameters to modify when needed

### Configurable parameters

- The number of results shown per row in UI layout: default as 5. Change it by exporting this environment variable and re-deploy the application

  ```bash
  export  SHOW_RESULT_PER_ROW=10
  ```

- Deduplicate switch and threshold: deduplicate switch decides whether or not to enable deduplication for similar search results. Note that this function currently supports video only. Once enabled, video search results that are the same video and start within the interval of threshold would be deduplicated. Only one remains. For example:

![Search without deduplicate](./_assets/deduplicate_before.png)\
*Figure 1: Search without deduplication*

![Search with deduplicate](./_assets/deduplicate_after.png)\
*Figure 2: Search with deduplication*

Without deduplication enabled, the first row of results are from the same video, and the time difference among them are less than 5 seconds. Therefore, when deduplication is ticked, search button returns only one result from that video.

## Learn More

- Deploy the application with the [Get Started](./get-started.md).
- Understand the components, services, architecture, and data flow, in
  the [Overview](./index.md).
