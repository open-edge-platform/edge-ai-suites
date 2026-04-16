# Wind Turbine Anomaly Detection — New Training & Inference (Intel GPU-Accelerated)

This guide covers the **new approach** that eliminates LinearRegression validation, uses physics-aware thresholds, and runs on Intel GPU via `sklearnex`.

## Quick Start

### 1. Environment Setup

```bash
cd training/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install dpctl  # For GPU offload support
```

### 2. Train Model (GPU-Accelerated)

```bash
source .venv/bin/activate
python train_anomaly_simgeneric.py \
  --data T1.csv \
  --features wind_speed \
  --output-model rf_anomaly_model_compact.pkl \
  --n-estimators 50 \
  --max-depth 15 \
  --device gpu
```

**Output**: `rf_anomaly_model_compact.pkl` (1.3 MB, 82.4% smaller than original)

**Performance**:
- R² score: 0.9062 (vs original 0.9063)
- RMSE: 400.01
- Training time: GPU-accelerated

### 3. Run Inference (Row-by-Row, GPU)

```bash
source .venv/bin/activate
python infer_anomaly_simgeneric.py \
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

---

## What Changed

### Training (New Script: `train_anomaly_simgeneric.py`)

| Aspect | Old | New |
|---|---|---|
| Features | wind_speed, direction, theoretical curve | wind_speed only |
| Trees | 350 | 50 |
| Max depth | 25 (unlimited) | 15 (regularized) |
| Model size | 7.4 MB | 1.3 MB |
| Data type | float64 | **explicit float32** |
| GPU support | None | ✅ `dpctl.SyclQueue("gpu")` |

### Inference (New Script: `infer_anomaly_simgeneric.py`)

| Aspect | Old (Notebook) | New |
|---|---|---|
| LinearRegression | ✅ validation with `coef < 200` | ❌ **removed** |
| Sliding window | 3 consecutive points | ❌ **removed** (row-by-row) |
| Error formula | `(pred - actual) / actual` | `(pred - actual) / pred` (stable) |
| Operating range | ✅ physics filters | ✅ physics filters |
| Error threshold | 0.15 (15%) | 0.15 (15%) |
| Severity bins | error < 30/60/100  | error < 30/60 (%, same) |
| Anomalies flagged | ~5% of data | ~5% of data (\*fewer false positives\*) |

---

## Detailed Usage

### Training

#### CLI Arguments

```bash
python train_anomaly_simgeneric.py \
  --data T1.csv \
  --target grid_activepower \
  --features wind_speed \
  --output-model rf_model.pkl \
  --test-size 0.2 \
  --random-state 42 \
  --n-estimators 50 \
  --max-depth 15 \
  --device cpu  # or 'gpu'
```

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

#### Example: CPU Training (Smaller Model)

```bash
python train_anomaly_simgeneric.py \
  --data T1.csv \
  --features wind_speed \
  --output-model rf_compact.pkl \
  --n-estimators 30 \
  --max-depth 10 \
  --device cpu
```

### Inference

#### CLI Arguments

```bash
python infer_anomaly_simgeneric.py \
  --model rf_anomaly_model_compact.pkl \
  --data ../simulation-data/wind-turbine-anomaly-detection.csv \
  --output anomalies_predictions.csv \
  --device gpu \
  --cut-in-speed 3.0 \
  --cut-out-speed 14.0 \
  --min-power 50.0 \
  --error-threshold 0.15
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

#### Physics-Based Filtering

Points are **skipped** (marked as NORMAL, anomaly_status = NaN) if:
1. Wind speed ≤ cut_in_speed (3 m/s) — turbine not generating
2. Wind speed > cut_out_speed (14 m/s) — turbine stopped
3. Wind speed > cut_in_speed AND power < min_power (50 kW) — operator curtailment/maintenance

#### Error Thresholds

Once a point passes physics filter, anomaly is flagged if `relative_error > 0.15`:
- **LOW**: 15% < error < 30% (small deviation)
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

---

## Why This New Approach?

### Problems with Old Approach

1. **LinearRegression validation**: 
   - Fits LR to only 3 points → huge variance
   - Magic threshold (`coef < 200`) → not data-driven
   - Added complexity without benefit

2. **Sliding window**:
   - Misses isolated anomalies
   - Requires consecutive anomalies

3. **Overfitted model**:
   - 350 trees, unlimited depth
   - High variance on field data

### Solutions (New Approach)

✅ **No LinearRegression** — direct per-point severity classification  
✅ **Row-by-row processing** — catches all anomalies  
✅ **Regularized model** — 50 trees, max_depth=15, 82.4% smaller  
✅ **Physics-aware** — respects turbine operating range  
✅ **Stable error formula** — works with near-zero actual power  
✅ **GPU-accelerated** — Intel `sklearnex` + `dpctl.SyclQueue`  
✅ **Explicit float32** — consistent precision throughout  

---

## Integration with UDF (`windturbine_anomaly_detector.py`)

The runtime Kapacitor UDF now uses the **same inference logic**:

```python
# Per-point, no sliding window
if error > error_threshold:
    if error < 0.3:
        point.fieldsDouble["anomaly_status"] = 0.3  # LOW
    elif error < 0.6:
        point.fieldsDouble["anomaly_status"] = 0.6  # MEDIUM
    else:
        point.fieldsDouble["anomaly_status"] = 1.0  # HIGH
```

No LinearRegression dependency in production.

---

## File Listing

| File | Purpose |
|---|---|
| `train_anomaly_simgeneric.py` | Training script (new approach) |
| `infer_anomaly_simgeneric.py` | Inference script (new approach) |
| `rf_anomaly_model_compact.pkl` | Pre-trained compact model (1.3 MB) |
| `anomalies_final_predictions.csv` | Example inference output |
| `APPROACH_COMPARISON.md` | Detailed comparison: old vs new |
| `requirements.txt` | Python dependencies |
| `T1.csv` | Training data (50,530 rows) |
| `windturbine_anomaly_detection.ipynb` | Original notebook (for reference) |

---

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

## References

- [Approach Comparison](APPROACH_COMPARISON.md)
- [Original Notebook](windturbine_anomaly_detection.ipynb)
