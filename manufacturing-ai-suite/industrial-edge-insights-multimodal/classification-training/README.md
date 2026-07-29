# Weld Defect Classifier - ML Pipeline

Multi-class machine learning pipeline that classifies weld defects from sensor readings. The training script loads data from a manifest-driven dataset split, trains on TRAIN+VAL, evaluates on TEST, and exports model artifacts for row-by-row inference.

---

## Table of Contents

- [Overview](#overview)
- [Defect Categories](#defect-categories)
- [Input Features](#input-features)
- [Project Files](#project-files)
- [Required Model Artifacts](#required-model-artifacts)
- [Setup](#setup)
- [Training the Model](#training-the-model)
- [Data Loading Rules](#data-loading-rules)
- [Running Inference](#running-inference)
  - [Sample Inference Script](#1-sample-inference-script-recommended)
  - [Predictor CLI](#2-predictor-cli)
  - [Programmatic API](#3-programmatic-api)
- [Model Performance](#model-performance)
- [Intel Acceleration](#intel-acceleration)
- [Output Format](#output-format)

---

## Overview

The training pipeline builds a **RandomForestClassifier** for 12 weld quality categories (including **Good Weld**) using manifest-indexed dataset rows. It uses:

- Training split: `TRAIN + VAL`
- Evaluation split: `TEST`
- Feature filter: drops rows where `Primary Weld Current < 50.0`

Intel acceleration is enabled via **Intel Extension for Scikit-learn** (`scikit-learn-intelex`) when installed.

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

### Key correlations from Exploratory Data Analysis

- **Pressure** is universally **negatively correlated** with CO₂ Flow and Primary Current — rising pressure is a consistent defect indicator.
- **Excessive Penetration** has the highest CO₂ Flow (mean 18.95 L/min) and highest Secondary Voltage (mean 24.1 V).
- **Undercut** shows the highest Feed (mean 114.4 m/min) and highest Primary Current (mean 202.3 A).
- **Porosity** categories show near-zero Pressure and CO₂ Flow — characteristic of process interruption.
- **Good Weld** has the lowest Pressure (mean 0.40) and lowest CO₂ Flow (mean 3.21) among all categories.

---

## Project Files

```
weld_defect_train.py            # Training script — produces model Artifacts
weld_defect_predict.py          # WeldDefectPredictor class + CLI
weld_defect_inference_sample.py # Standalone sample inference script

weld_defect_detector.pkl        # Trained sklearn pipeline   (generated)
weld_defect_detector_labels.pkl # LabelEncoder mapping       (generated)
weld_defect_detector.json       # Model metadata             (generated)
weld_defect_detector.txt        # Evaluation report          (generated)
```

---

## Required Model Artifacts

Both generated pickle files are required for correct inference in this project:

1. `weld_defect_detector.pkl`
   - Serialized sklearn pipeline (scaler + classifier)
   - Produces numeric class predictions and probability vectors

2. `weld_defect_detector_labels.pkl`
   - Serialized `LabelEncoder`
   - Maps numeric class index back to defect category text
   - Provides correct class order for probability decoding

### Why both are needed

- The model predicts an integer class index (for example `3`), not category text.
- The labels file converts that index to a human-readable class (for example `Excessive Penetration`).
- Probability arrays from `predict_proba()` follow label order, so the label mapping is needed to build the `probabilities` dictionary correctly.

### If one file is missing

- Missing `weld_defect_detector.pkl`:
  Inference cannot run.
- Missing `weld_defect_detector_labels.pkl`:
  You may still get numeric outputs, but category names and per-class probability labels will be wrong or unavailable.

In short: keep `weld_defect_detector.pkl` and `weld_defect_detector_labels.pkl` together when deploying.

### Current inference-script compatibility note

The current inference scripts (`weld_defect_predict.py` and `weld_defect_inference_sample.py`) still default to:

- `weld_defect_model.pkl`
- `weld_defect_labels.pkl`
- `model_info.json` (optional in the sample script)

If you train with the current training script, either rename/copy generated artifacts to those names or update the inference script constants.

Example compatibility copy:

```bash
cp weld_defect_detector.pkl weld_defect_model.pkl
cp weld_defect_detector_labels.pkl weld_defect_labels.pkl
cp weld_defect_detector.json model_info.json
```

---

## Setup

### Requirements

- Python 3.10 is required for training.

```bash
rm -rf venv
/usr/bin/python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Data

Training data source:
- https://huggingface.co/datasets/IntelLabs/Intel_Robotic_Welding_Multimodal_Dataset

For more detailed dataset information, see:
- [Intel Robotic Welding Multimodal Dataset (Hugging Face)](https://huggingface.co/datasets/IntelLabs/Intel_Robotic_Welding_Multimodal_Dataset)

After downloading and extracting the dataset, set the training data root to the extracted folder that contains `manifest.csv`.

Example extracted path:
```
/home/<user>/datasets/intel_robotic_welding_dataset
```

Run training by pointing `DATA_DIR` to that path:
```bash
DATA_DIR=/home/<user>/datasets/intel_robotic_welding_dataset python3.10 weld_defect_train.py
```

If `DATA_DIR` is not set, the script uses its built-in default path.

Each source CSV should contain the model features: `Pressure`, `CO2 Weld Flow`, `Feed`, `Primary Weld Current`, `Secondary Weld Voltage`.

---

## Data Loading Rules

`weld_defect_train.py` reads `manifest.csv`, filters rows to `STEEL_TYPE == FE410`, normalizes split names, and resolves folders/CSVs from manifest columns.

Expected manifest fields (case-insensitive aliases are supported):

- Split column: one of `SPLIT`, `SET`, `DATASET`, `SUBSET`
- Steel column: one of `STEEL_TYPE`, `STEEL`, `MATERIAL`, `MATERIAL_TYPE`, `GRADE`
- Optional directory columns:
  - `SUBDIRS` / `SUBDIR` / `PATH`
  - `DIRECTORY` / `DIR` / `DATA_DIR` / `FOLDER`
- Optional category column: `CATEGORY` / `CLASS` / `LABEL` / `TARGET` / `DEFECT`

Important behavior:

- Only normalized splits `TRAIN`, `VAL`, `TEST` are used.
- At least one TRAIN and one VAL source must resolve, otherwise training exits with error.
- For each manifest row folder, the loader expects exactly one CSV file.
- TEST rows with classes not seen in TRAIN+VAL are dropped with a warning.
- Rows with `Primary Weld Current < 50.0` are removed from both train and test sets.

---

## Training the Model

```bash
python3.10 weld_defect_train.py
```

This will:
1. Resolve dataset files from `manifest.csv` for steel type `FE410`
2. Build TRAIN+VAL training data and TEST evaluation data
3. Train a `Pipeline(StandardScaler -> RandomForestClassifier)`
4. Evaluate on TEST and write report to `weld_defect_detector.txt`
5. Save `weld_defect_detector.pkl`, `weld_defect_detector_labels.pkl`, `weld_defect_detector.json`

Model/training configuration in the current script:

- `RandomForestClassifier(n_estimators=60, max_depth=14, min_samples_leaf=8, max_features="sqrt", random_state=42, n_jobs=-1)`
- Artifact compression: `joblib` with `("xz", 3)`
- Max allowed model size: `100 MB`

**Sample output:**

```
Starting weld defect training
Loaded manifest data (files=..., train+val_rows=..., test_rows=...)
Training model...
Evaluating on TEST...
TEST Accuracy: ...
Saved report: weld_defect_detector.txt
Saved model artifacts: weld_defect_detector.pkl, weld_defect_detector_labels.pkl, weld_defect_detector.json
Done
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
# Automatic target
python weld_defect_inference_sample.py --device auto

# Script default (if --device is omitted): gpu
python weld_defect_inference_sample.py

# Force CPU offload target
python weld_defect_inference_sample.py --device cpu

# Request Intel iGPU offload
python weld_defect_inference_sample.py --device gpu
```

Notes:
- Current script default is `--device gpu` when omitted.
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

This version of the training script does not run cross-validation. It reports TEST-set metrics from manifest splits.

Where to check results:

- `weld_defect_detector.txt`: full classification report + confusion matrix
- console output: TEST accuracy
- `weld_defect_detector.json`: metadata (`classes`, `features`, `trained_at`, `intel_patched`, data-source fields)

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
| `explanation` | `dict` | Human-readable explanation block with reason + top evidence |

### Explanation object

| Field | Type | Description |
|---|---|---|
| `reason` | `str` | Natural-language rationale for predicted class |
| `top_probabilities` | `list[dict]` | Top-N ranked class probabilities |
| `top_signal_features` | `list[dict]` | Most influential feature comparisons used in explanation |

### How to read `top_probabilities`

Each item has:

- `category`: class label
- `probability`: model probability for that class

Interpretation tips:

- The first item should match `predicted_category` and typically has the same value as `confidence`.
- If rank-1 and rank-2 probabilities are close, the prediction is less decisive.
- If rank-1 is much larger than the rest, the prediction is more stable.
- The list is mainly for quick triage and operator visibility into near-miss classes.

Example pattern:

- High certainty: `[0.88, 0.06, 0.03]`
- Ambiguous case: `[0.41, 0.38, 0.15]`

### How to read `top_signal_features`

Each item includes:

- `feature`: input feature name
- `value`: observed value from the incoming row
- `predicted_mean`: class-profile mean for the predicted class
- `good_weld_mean`: reference mean for Good Weld
- `evidence_score`: relative support score for predicted class vs Good Weld

Interpretation tips:

- Positive `evidence_score` means the feature is closer to the predicted class profile than to Good Weld.
- Negative `evidence_score` means the feature is closer to Good Weld than the predicted class.
- Values near `0` indicate weak or neutral evidence from that feature.
- These are explanation signals, not SHAP-style causal attributions.

Operational use:

- Use `top_probabilities` to judge prediction certainty.
- Use `top_signal_features` to understand which sensor channels likely drove the decision.
- Combine both before triggering automated actions (for example, hard reject vs manual review).

### Example output

```json
{
  "predicted_category": "Good Weld",
  "is_defect": false,
  "defect_probability": 0.586889,
  "good_weld_probability": 0.413111,
  "confidence": 0.413111,
  "probabilities": {
    "Burnthrough": 0.062784,
    "Crater_Cracks": 0.01198,
    "Excessive_Convexity": 0.061574,
    "Excessive_Penetration": 0.074546,
    "Good Weld": 0.413111,
    "Lack_of_Fusion": 0.050077,
    "Overlap": 0.000407,
    "Porosity": 0.0,
    "Porosity_w_Excessive_Penetration": 0.0,
    "Spatter": 0.148899,
    "Undercut": 0.038421,
    "Warping": 0.138201
  },
  "explanation": {
    "reason": "Classified as Good Weld because key signals (Pressure, CO2 Weld Flow, Feed) align more with Good Weld profile than Good Weld profile.",
    "top_probabilities": [
      {
        "category": "Good Weld",
        "probability": 0.413111
      },
      {
        "category": "Spatter",
        "probability": 0.148899
      },
      {
        "category": "Warping",
        "probability": 0.138201
      }
    ],
    "top_signal_features": [
      {
        "feature": "Pressure",
        "value": 2.91,
        "predicted_mean": 0.180755,
        "good_weld_mean": 0.180755,
        "evidence_score": 0.0
      },
      {
        "feature": "CO2 Weld Flow",
        "value": 0.0,
        "predicted_mean": 16.68298,
        "good_weld_mean": 16.68298,
        "evidence_score": 0.0
      },
      {
        "feature": "Feed",
        "value": 6.07,
        "predicted_mean": 36.491665,
        "good_weld_mean": 36.491665,
        "evidence_score": 0.0
      }
    ]
  }
}
```
