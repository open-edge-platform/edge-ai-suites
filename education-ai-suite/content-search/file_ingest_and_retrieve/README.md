## Setup

### Prepare Python virtual environment

```cmd
python -m venv venv_py310
```

**Note:** Currently only Python version 3.10 has been verified on Windows. Please make sure you've installed the right version.

```cmd
venv_py310\Scripts\activate
pip install -r requirements.txt
```

Refer to [this guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/multimodal-embedding-serving/docs/user-guide/wheel-installation.md) to obtain the multimodal-embedding package wheel `multimodal_embedding_serving-0.1.1-py3-none-any.whl`.

```cmd
pip install multimodal_embedding_serving-0.1.1-py3-none-any.whl
```

Some dependencies need to be installed manually

```cmd
pip install git+https://github.com/apple/ml-mobileclip.git@c16bfe5a4feb424762d6bdf5245539120a4ce9ef#egg=mobileclip

pip install salesforce-lavis==1.0.2
```

### Start service

```cmd
uvicorn video_ingest_and_retrieve.server:app --host 0.0.0.0 --port 9990
```

Make sure MinIO and ChromaDB services are also up and running.

### Sample curl commands

- Ingest a file by bucket name + file path in MinIO

```
curl -X POST "http://127.0.0.1:9990/v1/dataprep/ingest" -H "Content-Type: application/json" -d "{\"bucket_name\": \"<your_bucket_name>\", \"file_path\": \"<your_file_path>\"}"
```


- Retrieve

```
curl -X POST "http://127.0.0.1:9990/v1/retrieval" -H "Content-Type: application/json" -d "{\"query\": \"<some_text_description>\", \"max_num_results\": 1}"
```