# Weld Defect Classifier — ML Pipeline

Multi-class machine learning pipeline that classifies weld defects from real-time sensor readings. Accepts sensor data row-by-row and outputs the predicted defect category along with per-class probabilities.

---

## Table of Contents

- [Overview](#overview)
- [Defect Categories](#defect-categories)
- [Input Features](#input-features)
- [Project Files](#project-files)
- [Required Model Artefacts](#required-model-artefacts)
- [Setup](#setup)
- [Training the Model](#training-the-model)
- [Running Inference](#running-inference)
  - [Sample Inference Script](#1-sample-inference-script-recommended)
  - [Predictor CLI](#2-predictor-cli)
  - [Programmatic API](#3-programmatic-api)
- [Model Performance](#model-performance)
- [Intel Acceleration](#intel-acceleration)
- [Output Format](#output-format)

---

## Overview

The pipeline trains a **RandomForestClassifier** on simulation sensor data and classifies each incoming sensor row into one of 12 weld quality categories — including a "Good Weld" class. It is accelerated by **Intel Extension for Scikit-learn** (`scikit-learn-intelex`), which routes computation through the **oneDAL backend**, enabling inference on Intel CPUs and iGPUs.

---

## Defect Categories

| # | Category | Description |
|---|---|---|
| 1 | **Good Weld** | No defect — baseline reference |
| 2 | **Burnthrough Weld** | Excessive heat burns through the base metal |
| 3 | **Crater Cracks** | Cracks formed at weld termination crater |
| 4 | **Excessive Convexity** | Weld bead too convex / high |
| 5 | **Excessive Penetration** | Weld penetrates too deep through the joint |
| 6 | **Lack of Fusion** | Incomplete fusion between weld and base metal |
| 7 | **Overlap** | Weld metal flows over base metal without fusing |
| 8 | **Porosity w/ EP** | Gas pockets combined with excessive penetration |
| 9 | **Porosity w/ Excessive Penetration** | Porosity co-occurring with deep penetration |
| 10 | **Spatter** | Metal droplets expelled from the weld pool |
| 11 | **Undercut** | Groove melted into base metal alongside the weld |
| 12 | **Warping Weld** | Distortion / warping of the welded component |

---

## Input Features

Five sensor channels are used — **order must be preserved** when calling the model:

| Column | Unit | Description |
|---|---|---|
| `Pressure` | bar | Shielding gas pressure |
| `CO2 Weld Flow` | L/min | CO₂ shielding gas flow rate |
| `Feed` | m/min | Wire feed speed |
| `Primary Weld Current` | A | Primary welding current |
| `Secondary Weld Voltage` | V | Secondary welding voltage |

### Key correlations from EDA

- **Pressure** is universally **negatively correlated** with CO₂ Flow and Primary Current — rising pressure is a consistent defect indicator.
- **Excessive Penetration** has the highest CO₂ Flow (mean 18.95 L/min) and highest Secondary Voltage (mean 24.1 V).
- **Undercut** shows the highest Feed (mean 114.4 m/min) and highest Primary Current (mean 202.3 A).
- **Porosity** categories show near-zero Pressure and CO₂ Flow — characteristic of process interruption.
- **Good Weld** has the lowest Pressure (mean 0.40) and lowest CO₂ Flow (mean 3.21) among all categories.

---

## Project Files

```
weld_defect_train.py            # Training script — produces model artefacts
weld_defect_predict.py          # WeldDefectPredictor class + CLI
weld_defect_inference_sample.py # Standalone sample inference script

weld_defect_model.pkl           # Trained sklearn pipeline  (generated)
weld_defect_labels.pkl          # LabelEncoder mapping       (generated)
model_info.json                 # Model metadata             (generated)
weld_defect_report.txt          # Evaluation report          (generated)
```

---

## Required Model Artefacts

Both generated pickle files are required for correct inference in this project:

1. `weld_defect_model.pkl`
   - Serialized sklearn pipeline (scaler + classifier)
   - Produces numeric class predictions and probability vectors

2. `weld_defect_labels.pkl`
   - Serialized `LabelEncoder`
   - Maps numeric class index back to defect category text
   - Provides correct class order for probability decoding

### Why both are needed

- The model predicts an integer class index (for example `3`), not category text.
- The labels file converts that index to a human-readable class (for example `Excessive Penetration`).
- Probability arrays from `predict_proba()` follow label order, so the label mapping is needed to build the `probabilities` dictionary correctly.

### If one file is missing

- Missing `weld_defect_model.pkl`:
  Inference cannot run.
- Missing `weld_defect_labels.pkl`:
  You may still get numeric outputs, but category names and per-class probability labels will be wrong or unavailable.

In short: keep `weld_defect_model.pkl` and `weld_defect_labels.pkl` together when deploying.

---

## Setup

### Requirements

```bash
pip install scikit-learn==1.6.1 scikit-learn-intelex joblib pandas numpy packaging setuptools
```

Or install directly from the local dependency file:

```bash
pip install -r requirements.txt
```

Or using the project virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install scikit-learn==1.6.1 scikit-learn-intelex joblib pandas numpy packaging setuptools
```

### Data

Training data is read from:
```
edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/
  weld-data-simulator/simulation-data/*.csv
```
Each CSV contains one defect category and columns: `Pressure`, `CO2 Weld Flow`, `Feed`, `Primary Weld Current`, `Wire Consumed`, `Secondary Weld Voltage`.

---

## Training the Model

```bash
python weld_defect_train.py
```

This will:
1. Load all 12 defect-category CSV files (3,920 rows total)
2. Run 5-fold stratified cross-validation
3. Generate a hold-out classification report → `weld_defect_report.txt`
4. Retrain on the full dataset
5. Save `weld_defect_model.pkl`, `weld_defect_labels.pkl`, `model_info.json`

**Sample output:**

```
Intel Extension for Scikit-learn: ENABLED (oneDAL backend)
Loaded 3,920 rows across 12 categories

[1/3] Running 5-fold stratified cross-validation …
      CV Accuracy: 0.9885 ± 0.0035

[2/3] Training on 80% hold-out split …
      Hold-out Accuracy: 0.9923

[3/3] Retraining on full dataset …
Model saved → weld_defect_model.pkl
```

---

## Running Inference

### 1. Sample Inference Script (recommended)

The cleanest way to run row-by-row inference. Loads the exported model and processes each sensor reading independently.

#### Demo mode (built-in sample rows)

```bash
python weld_defect_inference_sample.py
```

#### CSV mode — process a sensor data file row by row

```bash
python weld_defect_inference_sample.py path/to/sensor_data.csv
```

The CSV must contain the five feature columns (column names are case-sensitive):
```
Pressure,CO2 Weld Flow,Feed,Primary Weld Current,Secondary Weld Voltage
```

#### CSV mode — save annotated results

```bash
python weld_defect_inference_sample.py path/to/sensor_data.csv --out results.csv
```

The output CSV contains the original columns **plus**:
- `predicted_category`
- `is_defect`
- `defect_probability`
- `good_weld_probability`
- `confidence`

#### Device selection (CPU / GPU)

The sample script supports explicit device selection through `--device`:

```bash
# Automatic target (default)
python weld_defect_inference_sample.py --device auto

# Force CPU offload target
python weld_defect_inference_sample.py --device cpu

# Request Intel iGPU offload
python weld_defect_inference_sample.py --device gpu
```

Notes:
- `auto` uses the default oneDAL target.
- `cpu` and `gpu` use Intel `target_offload` configuration.
- If the environment has host-only oneDAL (no DPC backend), the script falls back to host CPU and prints:
  `Requested device offload but this oneDAL build is host-only (no DPC backend). Falling back to host CPU.`

---

### 2. Predictor CLI

Quick single-row inference. Values are positional: `Pressure CO2_Flow Feed Current Voltage`.

```bash
# Pass values directly
python weld_defect_predict.py 0.87 18.95 37.58 89.06 24.10

# Pipe a stream of rows (one per line, space- or comma-separated)
echo "0.87,18.95,37.58,89.06,24.10" | python weld_defect_predict.py --stdin

# Compact output for piped mode
cat sensor_stream.csv | python weld_defect_predict.py --stdin

# Interactive mode — prompts for each field
python weld_defect_predict.py
```

**Single-row JSON output example:**

```json
{
  "predicted_category": "Excessive Penetration",
  "is_defect": true,
  "defect_probability": 1.0,
  "good_weld_probability": 0.0,
  "confidence": 0.9886,
  "probabilities": {
    "Burnthrough Weld": 0.0,
    "Crater Cracks": 0.0,
    "Excessive Convexity": 0.0,
    "Excessive Penetration": 0.9886,
    "Good Weld": 0.0,
    "Lack of Fusion": 0.0075,
    "Overlap": 0.0,
    "Porosity w/ EP": 0.0,
    "Porosity w/ Excessive Penetration": 0.0,
    "Spatter": 0.0009,
    "Undercut": 0.0008,
    "Warping Weld": 0.0021
  }
}
```

---

### 3. Programmatic API

Import `WeldDefectPredictor` into any Python script:

```python
from weld_defect_predict import WeldDefectPredictor

# Load model once at startup
predictor = WeldDefectPredictor()

# Predict a single sensor row
result = predictor.predict_row(
    pressure=0.87,
    co2_weld_flow=18.95,
    feed=37.58,
    primary_weld_current=89.06,
    secondary_weld_voltage=24.10,
)
print(result["predicted_category"])   # "Excessive Penetration"
print(result["is_defect"])            # True
print(result["defect_probability"])   # 1.0
print(result["confidence"])           # 0.9886

# Predict from a dict (keys must match feature names exactly)
row = {
    "Pressure": 0.40,
    "CO2 Weld Flow": 3.21,
    "Feed": 38.88,
    "Primary Weld Current": 98.69,
    "Secondary Weld Voltage": 15.81,
}
result = predictor.predict_from_dict(row)

# Batch predict an entire DataFrame
import pandas as pd
df = pd.read_csv("sensor_data.csv")
annotated_df = predictor.predict_dataframe(df)
```

Using the low-level `predict_row()` from the inference sample script:

```python
import joblib
from weld_defect_inference_sample import load_model, predict_row

pipeline, le = load_model()   # load once

# call for every incoming sensor reading
result = predict_row(pipeline, le,
    pressure=2.91,
    co2_weld_flow=0.0,
    feed=6.07,
    primary_weld_current=0.0,
    secondary_weld_voltage=81.91,
)
print(result)
```

---

## Model Performance

| Metric | Value |
|---|---|
| Algorithm | RandomForestClassifier (300 trees) |
| 5-fold CV Accuracy | **98.85% ± 0.35%** |
| Hold-out Accuracy | **99.23%** |
| Macro F1 | **0.9915** |
| Weighted F1 | **0.9923** |
| Training rows | 3,920 across 12 classes |

### Per-class hold-out results

| Category | Precision | Recall | F1 |
|---|---|---|---|
| Burnthrough Weld | 1.000 | 0.970 | 0.985 |
| Crater Cracks | 0.984 | 0.984 | 0.984 |
| Excessive Convexity | 1.000 | 1.000 | 1.000 |
| Excessive Penetration | 0.975 | 1.000 | 0.987 |
| Good Weld | 1.000 | 1.000 | 1.000 |
| Lack of Fusion | 0.984 | 0.968 | 0.976 |
| Overlap | 0.974 | 0.974 | 0.974 |
| Porosity w/ EP | 1.000 | 1.000 | 1.000 |
| Porosity w/ Excess. Penet. | 1.000 | 1.000 | 1.000 |
| Spatter | 0.984 | 1.000 | 0.992 |
| Undercut | 1.000 | 1.000 | 1.000 |
| Warping Weld | 1.000 | 1.000 | 1.000 |

---

## Intel Acceleration

The pipeline uses **Intel Extension for Scikit-learn** (`scikit-learn-intelex`) to accelerate training and inference via the **oneDAL** (Intel oneAPI Data Analytics Library) backend.

- `RandomForestClassifier` and `StandardScaler` are both in the Intel patch map and receive hardware acceleration automatically.
- The patch is applied **before any sklearn import**, which is required for the acceleration to take effect.
- Works on **Intel CPUs** (AVX-512 vectorisation) and **Intel iGPUs** (via oneDNN).
- Falls back silently to standard scikit-learn if the package is not installed — no code changes needed.
- Explicit device targeting in the sample script is available via `--device auto|cpu|gpu`.

```python
# Applied automatically in all three scripts:
from sklearnex import patch_sklearn
patch_sklearn(verbose=False)
# ... sklearn imports follow
```

To verify the backend is active at runtime, check the console output:
```
Intel Extension for Scikit-learn: ENABLED  (oneDAL / Intel iGPU backend)
```

---

## Output Format

Every prediction returns a dict with the following fields:

| Field | Type | Description |
|---|---|---|
| `predicted_category` | `str` | Most likely defect class name |
| `is_defect` | `bool` | `False` only when `predicted_category == "Good Weld"` |
| `defect_probability` | `float` | `1 − P(Good Weld)` — overall defect likelihood |
| `good_weld_probability` | `float` | `P(Good Weld)` |
| `confidence` | `float` | Probability of the predicted class |
| `probabilities` | `dict[str, float]` | Per-class probability for all 12 categories |
