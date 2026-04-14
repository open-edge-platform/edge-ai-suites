## Setup

### Prepare Python virtual environment

```cmd
python -m venv venv_chroma
```

**Note:** Currently only Python version 3.10 has been verified on Windows. Please make sure you've installed the right version.

```cmd
venv_chroma\Scripts\activate
pip install chromadb==1.4.1
```

### Start service

```cmd
chroma run --host 0.0.0.0 --port 9090 --path ./chroma-data
```