# Run Without Docker

Use this path when you want to run the service directly with Python on the host.

## Python Setup

From the `rag-service/` directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Config

- Start from `config.yaml`.
- Use `SMART_KIOSK_RAG_CONFIG_OVERRIDE_PATHS` for one or more YAML override files.
- Use `SMART_KIOSK_RAG__...` environment variables for targeted overrides.
- For Intel GPU use, make sure the host has the required OpenVINO runtime stack and set `models.llm.device: GPU`.

## Start

```bash
source .venv/bin/activate
python main.py
```

Default bind address:

- host: `0.0.0.0`
- port: `8020`

Equivalent `uvicorn` command:

```bash
uvicorn main:app --host 0.0.0.0 --port 8020
```

## Verify

```bash
curl --noproxy '*' http://127.0.0.1:8020/health
```

## Notes

- Model bootstrap runs on startup through `utils/ensure_model.py`.
- LLM and embedding assets are cached under `models/` by default.
- Ingested vectors and Chroma files are stored under `storage/vector_db/`.
