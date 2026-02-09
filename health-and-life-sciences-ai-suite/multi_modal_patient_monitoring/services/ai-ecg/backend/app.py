from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import time
from inference.engine import ECGInferenceEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title="ECG OpenVINO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ECGInferenceEngine()

# ---- STREAM STATE (VERY IMPORTANT) ----
stream_files = []
stream_index = 0


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_ecg(file: UploadFile = File(...)):
    if not file.filename.endswith(".mat"):
        raise HTTPException(status_code=400, detail="Only .mat files are allowed")

    file_path = os.path.join(DATA_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    return {"status": "uploaded", "filename": file.filename}


@app.get("/predict/{filename}")
def predict_ecg(filename: str):
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        pred = engine.predict(filename)
        return {
            "file": filename, 
            "signal": pred["signal"],
            "result": pred["result"],
            "inference_ms": pred["inference_ms"],
            "length": len(pred["signal"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------- NEW TRUE STREAMING ENDPOINT --------
@app.get("/predict_stream_next")
def predict_stream_next():
    """
    Returns ONE file inference per call.
    Cycles through files endlessly.
    """
    global stream_files, stream_index

    if not stream_files:
        stream_files = sorted(
            [f for f in os.listdir(DATA_DIR) if f.endswith(".mat")]
        )
        stream_index = 0

    if not stream_files:
        raise HTTPException(status_code=404, detail="No .mat files found")

    filename = stream_files[stream_index]
    stream_index = (stream_index + 1) % len(stream_files)

    pred = engine.predict(filename)

    return {
        "file": filename,
        "signal": pred["signal"],
        "result": pred["result"],
        "inference_ms": pred["inference_ms"],
        "length": len(pred["signal"]),
    }
