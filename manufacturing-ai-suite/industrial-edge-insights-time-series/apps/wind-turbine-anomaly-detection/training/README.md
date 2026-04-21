# Wind Turbine Anomaly Detection — Training & Inference Sample (Intel GPU-Accelerated)

The wind turbine anomaly model is built using `train.py` for model training and `inference_sample.py` for inference.
The dataset file is [T1.csv](T1.csv), sourced from https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset.

## Quick Start

### 1. Environment Setup

```bash
cd training/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Train Model (GPU-Accelerated)

```bash
python train.py \
  --data T1.csv \
  --target grid_activepower \
  --features wind_speed \
  --output-model rf_model.pkl \
  --device cpu  # or 'gpu'
```

**Output**: `rf_model.pkl` (7.1 MB)

| Argument | Type | Default | Description |
|---|---|---|---|
| `--data` | Path | `T1.csv` | Training CSV file |
| `--target` | str | `grid_activepower` | Target column (actual power) |
| `--features` | str list | `["wind_speed"]` | Feature columns (space-separated) |
| `--output-model` | Path | `rf_anomaly_model.pkl` | Output model file |
| `--test-size` | float | 0.2 | Test split ratio |
| `--random-state` | int | 42 | Random seed for reproducibility |
| `--n-estimators` | int | 300 | Number of trees |
| `--max-depth` | int | None | Max tree depth (None = unlimited) |
| `--device` | str | `cpu` | `cpu` or `gpu` for offload |

#### Training a compact model 

```bash
python train.py \
  --data T1.csv \
  --target grid_activepower \
  --features wind_speed \
  --output-model rf_anomaly_model_compact.pkl \
  --test-size 0.2 \
  --random-state 42 \
  --n-estimators 50 \
  --max-depth 15 \
  --device cpu  # or 'gpu'
```

**Output**: `rf_anomaly_model_compact.pkl` (1.3 MB, 82.4% smaller than original)

**Performance**:
- R² score: 0.9062 (vs original 0.9063)
- RMSE: 400.01
- Training time: GPU-accelerated

### 3. Run Inference (Row-by-Row, GPU)

```bash
source .venv/bin/activate
python inference_sample.py \
  --model rf_model.pkl \
  --data ../simulation-data/wind-turbine-anomaly-detection.csv \
  --device gpu \
  --output anomalies_final_predictions.csv
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `--model` | Path | `rf_anomaly_model.pkl` | Trained model file |
| `--data` | Path | `../simulation-data/wind-turbine-anomaly-detection.csv` | Input CSV for inference |
| `--output` | Path | `anomaly_predictions.csv` | Output CSV |
| `--device` | str | `cpu` | `cpu` or `gpu` for offload |
| `--cut-in-speed` | float | 3.0 | Min wind speed (m/s) for generation |
| `--cut-out-speed` | float | 14.0 | Max wind speed (m/s) for generation |
| `--min-power` | float | 50.0 | Min power threshold (kW) in range |
| `--error-threshold` | float | 0.15 | Relative error > threshold = anomaly |


#### Using a compact model

```bash
source .venv/bin/activate
python inference_sample.py \
  --model rf_anomaly_model_compact.pkl \
  --data ../simulation-data/wind-turbine-anomaly-detection.csv \
  --device gpu \
  --output anomalies_final_predictions.csv
```

**Output**: CSV with columns:
- `wind_speed`, `grid_active_power`: Input data
- `predicted_power`: Model prediction
- `relative_error`: (predicted - actual) / predicted
- `anomaly_status`: `LOW`, `MEDIUM`, `HIGH`, or `NaN` (not anomalous)

#### Physics-Based Filtering

Points are **skipped** (marked as NORMAL, anomaly_status = NaN) if:
1. Wind speed ≤ cut_in_speed (3 m/s) — turbine not generating
2. Wind speed > cut_out_speed (14 m/s) — turbine stopped
3. Wind speed > cut_in_speed AND power < min_power (50 kW) — operator curtailment/maintenance

#### Error Thresholds

Once a point passes physics filter, anomaly is flagged if `relative_error > 0.1`:
- **LOW**: 10% < error < 30% (small deviation)
- **MEDIUM**: 30% < error < 60% (moderate deviation)
- **HIGH**: error > 60% (severe deviation)

---

## Output Format

### Training Output

```
Training completed.
Features: ['wind_speed']
Offload device: <dpctl.SyclQueue at 0x...>
X dtype: float32, y dtype: float32
RMSE: 400.0092
MAE : 162.8197
R2  : 0.9062
Saved model: rf_anomaly_model_compact.pkl
```

### Inference Output CSV

| Column | Type | Description |
|---|---|---|
| `wind_speed` | float | Input: wind speed (m/s) |
| `grid_active_power` | float | Input: actual power generated (kW) |
| `predicted_power` | float32 | Model prediction (kW) |
| `relative_error` | float32 | (predicted - actual) / predicted |
| `anomaly_status` | str/NaN | `LOW`, `MEDIUM`, `HIGH`, or NaN |

### Example Anomaly Detection Summary

```
Inference completed (row-by-row).
Offload device: <dpctl.SyclQueue at 0x...>
Input dtype sample: float32
Error threshold: 0.15 (15%)
Operating range: wind 3.0–14.0 m/s, min power 50.0 kW
Anomaly status breakdown: NORMAL=3272, LOW=33, MEDIUM=46, HIGH=125
Saved output: anomalies_final_predictions.csv
```

## Troubleshooting

### GPU Not Available?

```bash
# Check GPU backend
python -c "import dpctl; print(dpctl.get_devices('gpu'))"
```

If no GPU found, use `--device cpu` instead.

### Out of Memory During Training?

Reduce `--n-estimators` (try 20–50) or `--max-depth` (try 10).

### Many false positives in inference?

Increase `--error-threshold` (try 0.20 instead of 0.15).

### Missing anomalies?

Lower `--error-threshold` (try 0.10) or check operating range filters.

---