# Model Selection Guide: Wind Turbine Anomaly Detection

## Overview

Select and integrate your own ML models with our time-series analytics infrastructure.

**What You Can Do**:
- Use any model (Random Forest, XGBoost, Neural Networks, etc.)
- Any format (pkl, ONNX, PyTorch, TensorFlow, joblib, custom)
- Modify UDF to load/run your model
- Leverage GPU acceleration

---

## Application Context

**Problem**: Detect anomalies in wind turbine operations using real-time SCADA data
- **Input**: Wind Speed (m/s), Grid Active Power (kW)
- **Output**: Expected Grid Active Power (kW)
- **Deployment**: Edge infrastructure (CPU or GPU accelerated)
- **Framework**: Kapacitor UDF (User Defined Function)
- **Mode**: Single-point streaming only (live data, point-by-point)
- **No batch processing**: Each data point processed individually as it arrives

---

## Reference Implementation

**Current Model**: Random Forest Regressor (350 trees, max_depth=25)
- **File**: `windturbine_anomaly_detector.pkl`
- **Performance**: MAE < 50 kW, R² > 0.95
- **Why**: Good balance of accuracy, speed, and interpretability

**You can replace this with any model** - see integration section below.

---

### Quick Start Code

```python
# XGBoost with GPU
from xgboost import XGBRegressor
model = XGBRegressor(n_estimators=350, max_depth=25, tree_method='gpu_hist')

# LightGBM with GPU
from lightgbm import LGBMRegressor
model = LGBMRegressor(n_estimators=350, max_depth=25, device='gpu')

# Simple Polynomial
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
poly = PolynomialFeatures(degree=3)
model = LinearRegression()

# PyTorch MLP
import torch.nn as nn
class WindTurbineNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(1, 64), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 1)
        )
    def forward(self, x): return self.net(x)
```

---

## Model Integration

### Supported Serialization Formats

```python
# 1. Pickle/Joblib (sklearn models)
import pickle, joblib
pickle.dump(model, open('model.pkl', 'wb'))
model = pickle.load(open('model.pkl', 'rb'))

# 2. ONNX (cross-platform)
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
onnx_model = convert_sklearn(model, initial_types=[('input', FloatTensorType([None, 1]))])

# 3. PyTorch
torch.save(model.state_dict(), 'model.pt')
model.load_state_dict(torch.load('model.pt'))

# 4. TensorFlow
model.save('model')
model = tf.keras.models.load_model('model')

# 5. OpenVINO (Intel hardware optimization)
# Use mo tool to convert ONNX/PyTorch/TF to IR format
```

### Update UDF for Your Model

Edit `windturbine_anomaly_detector.py`:

```python
# 1. Update loading
def load_model(filename, format=None):
    """
    Load a model from disk.

    Parameters
    ----------
    filename : str
        Path to the model file.
    format : str, optional
        Model format: "pkl", "onnx", "pt"/"torch". If None, inferred from file extension.
    """
    import os

    # Infer format from file extension if not provided
    if format is None:
        _, ext = os.path.splitext(filename)
        format = ext.lstrip(".").lower()

    # Pickle (default)
    if format in ("pkl", "pickle", ""):
        import pickle
        with open(filename, "rb") as f:
            return pickle.load(f)

    # ONNX
    # elif format == "onnx":
    #     import onnxruntime as rt
    #     return rt.InferenceSession(filename)

    # PyTorch
    # elif format in ("pt", "torch"):
    #     import torch
    #     model = YourModelClass()
    #     model.load_state_dict(torch.load(filename))
    #     return model.eval()

    # Unknown / unsupported format
    raise ValueError(f"Unsupported model format: {format!r}")
# 2. Update inference (single point only)
y_pred = self.model.predict(np.reshape(x, (-1, 1)))  # sklearn - single point
# y_pred = self.model.run(None, {'input': x})[0]  # ONNX - single point
# y_pred = self.model(torch.tensor([[x]])).item()  # PyTorch - single point

# Note: Batch inference NOT supported - process one point at a time
```

### Update config.json

```json
{
    "udfs": {
        "name": "windturbine_anomaly_detector",
        "models": "your_model.pkl",  // or .onnx, .pt, etc.
        "device": "gpu"  // or "cpu"
    }
}
```

### Intel Optimizations

```python
# For sklearn models - significant speedup
from sklearnex import patch_sklearn
patch_sklearn()

# For deep learning - use OpenVINO
# Converts models to optimized IR format for Intel hardware
```

---

## Model Performance Requirements

### Performance Testing Protocol

1. **Split Data**: 70% train, 30% test
2. **Cross-Validation**: 5-fold CV on training set
3. **Test Set**: Never used during training/tuning
4. **Hardware Testing**: Profile on target edge device (both CPU and GPU)
5. **Load Testing**: Simulate 10+ concurrent turbine streams (each processing single points)
6. **GPU Efficiency**: Measure GPU memory usage and utilization

**GPU-Specific Tests**:
- Monitor VRAM consumption during streaming inference
- Test CPU fallback behavior if GPU unavailable
- Benchmark GPU vs CPU for single-point inference
- Verify multi-stream concurrent processing (10+ turbines)

---

## Data Requirements

**Training Data**: 10k-50k samples minimum, 6+ months coverage

**Preprocessing** (remove these points):
- Wind speed < 3 m/s or > 14 m/s (cut-in/cut-out)
- Power < 50 kW when 3 < wind_speed < 14 (curtailment)
- NaN/missing values
- Known anomalies (use separate validation set)

```python
def preprocess(df):
    df = df.dropna()
    return df[
        (df['wind_speed'] >= 3) & (df['wind_speed'] <= 14) &
        (df['grid_activepower'] >= 50)
    ]
```

**Additional Features** (optional): wind direction, temperature, blade pitch, rotor speed

---

## Using Your Own Dataset

### Dataset Requirements

Your dataset should contain:
- **Required columns**: `wind_speed`, `grid_activepower` (or equivalent power output column)
- **Optional columns**: `timestamp`, `wind_direction`, `temperature`, blade pitch, rotor speed
- **Format**: CSV, Parquet, or any pandas-readable format
- **Size**: 10k-50k samples minimum for training

> **Note**: If you use a dataset different from the reference, you are responsible for training a model with the required feature set and aligning the preprocessing steps accordingly.

### Example Dataset Formats

**Current reference dataset** (`T1.csv`):
```csv
timestamp,grid_activepower,wind_speed,Theoretical_Power_Curve,Wind Direction (°)
01 01 2018 00:00,380.05,5.31,416.33,259.99
01 01 2018 00:10,453.77,5.67,519.92,268.64
```

**Your dataset** - adapt column names:
```csv
time,power_output,wind_speed_ms,temperature
2024-01-01 00:00:00,385.2,5.3,15.2
2024-01-01 00:10:00,448.1,5.6,15.4
```

### Changes Required for Your Dataset

**1. Update column names in training notebook**:

Edit `training/windturbine_anomaly_detection.ipynb`:

```python
# Original
X = df[['wind_speed']]
y = df[['Theoretical_Power_Curve']]  # or 'grid_activepower'

# Your dataset - update to match your column names
X = df[['wind_speed_ms']]  # or whatever your wind speed column is called
y = df[['power_output']]    # or your power column name
```

**2. Update preprocessing function**:

```python
def preprocess(df):
    # Map your column names to expected names
    df = df.rename(columns={
        'power_output': 'grid_activepower',
        'wind_speed_ms': 'wind_speed'
    })
    
    df = df.dropna()
    return df[
        (df['wind_speed'] >= 3) & (df['wind_speed'] <= 14) &
        (df['grid_activepower'] >= 50)
    ]
```

**3. Update data loading**:

```python
# Load your dataset
df = pd.read_csv('path/to/your_dataset.csv')

# If using different time format
df['timestamp'] = pd.to_datetime(df['time'])

# If you have multiple turbines, filter for specific one
df = df[df['turbine_id'] == 'T1']
```

**4. Adjust operational parameters** (if your turbine specs differ):

```python
# In training notebook and UDF (windturbine_anomaly_detector.py)
cut_in_speed = 3      # Your turbine's cut-in speed (m/s)
cut_out_speed = 14    # Your turbine's cut-out speed (m/s)
min_power_th = 50     # Minimum power threshold (kW)
error_threshold = 0.15  # Adjust based on your data
```

**5. Update simulation data** (optional):

Place your dataset in `simulation-data/`:
```bash
cp your_dataset.csv simulation-data/wind-turbine-anomaly-detection.csv
```

Update Telegraf config to read from your file:
```toml
# telegraf-config/Telegraf.conf
[[inputs.file]]
  files = ["simulation-data/your_dataset.csv"]
  data_format = "csv"
  csv_column_names = ["wind_speed", "grid_activepower"]  # Your columns
```

### Dataset Validation Checklist

Before training:
- [ ] Verify column names match expected format (or update code)
- [ ] Check data types (numeric for wind_speed and power)
- [ ] Validate wind speed range (typically 0-25 m/s)
- [ ] Check for missing values (< 5% recommended)
- [ ] Verify timestamp format if using temporal features
- [ ] Confirm power values are in kW (or convert to kW)
- [ ] Remove or separate known anomalies for validation
- [ ] Ensure sufficient samples in operational range (3-14 m/s)

### Multi-Turbine Datasets

If your dataset contains multiple turbines:

```python
# Option 1: Train separate models per turbine
for turbine_id in df['turbine_id'].unique():
    turbine_df = df[df['turbine_id'] == turbine_id]
    model = train_model(turbine_df)
    save_model(model, f'windturbine_{turbine_id}_v1.0.pkl')

# Option 2: Train single model with turbine as feature
X = df[['wind_speed', 'turbine_id_encoded']]
y = df['grid_activepower']
model = train_model(X, y)

# Option 3: Use shared model (assumes similar turbines)
df_combined = df  # Use all turbines together
model = train_model(df_combined)
```
---

## Testing Checklist

Before deploying:

**Accuracy**:
- [ ] MAE, RMSE, R² meet targets (see criteria table)
- [ ] Train/test gap < 5% (check overfitting)
- [ ] Test on labeled anomalies (FP/FN rates)

**Performance**:
- [ ] Inference < 10ms (avg of 1000 predictions)
- [ ] Concurrent streams work (test 10+ turbines)
- [ ] Model loads < 5 seconds

**Integration**:
- [ ] Model loads correctly in UDF
- [ ] Prediction interface works
- [ ] Config.json updated
- [ ] Works on target hardware

**Robustness**:
- [ ] Handles NaN/missing values
- [ ] Out-of-range inputs don't crash
- [ ] Memory usage acceptable


**Evaluation Script**:
```python
from sklearn.metrics import mean_absolute_error, r2_score
import time, numpy as np

def evaluate(model, X_test, y_test):
    # Accuracy
    y_pred = model.predict(X_test)
    print(f"MAE: {mean_absolute_error(y_test, y_pred):.2f} kW")
    print(f"R²: {r2_score(y_test, y_pred):.4f}")
    
    # Inference speed
    num_iters = 1000
    start = time.perf_counter()
    for _ in range(num_iters):
        model.predict(X_test[:1])
    elapsed = time.perf_counter() - start
    avg_latency_ms = (elapsed / num_iters) * 1000
    print(f"Avg latency per inference: {avg_latency_ms:.2f} ms")
```

---

## Retraining Guidelines

**When to Retrain**:
- MAE increases >20% from baseline
- False positive rate >50% increase
- New turbine model/configuration
- Quarterly (recommended schedule)
- After 3-6 months new data

**Process**:
1. Collect 6-12 months operational data
2. Remove maintenance periods, validate quality
3. Train with same pipeline, compare vs current
4. A/B test on subset (1-2 weeks)
5. Gradual rollout: 10% → 50% → 100%

**Version Control**: `windturbine_anomaly_detector_vX.Y.<format>`
- X = algorithm change
- Y = retrain same algorithm

---

## Appendix: Hyperparameter Tuning Guidance

### Random Forest Tuning

**Key Hyperparameters**:

1. **`n_estimators`** (number of trees):
   - Default: 350
   - Range: 100-500
   - Higher = better accuracy but larger model size
   - Diminishing returns after ~300-400

2. **`max_depth`** (tree depth):
   - Default: 25
   - Range: 10-30
   - Higher = risk of overfitting
   - Lower = underfitting

3. **`min_samples_split`**:
   - Default: 2
   - Range: 2-10
   - Higher = prevents overfitting but may underfit

4. **`min_samples_leaf`**:
   - Default: 1
   - Range: 1-5
   - Higher = smoother predictions

5. **`max_features`**:
   - Default: 'sqrt'
   - Options: 'sqrt', 'log2', None
   - Controls feature sampling per split

**Tuning Template**:
```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [200, 350, 500],
    'max_depth': [20, 25, 30],
    'min_samples_split': [2, 5],
    'min_samples_leaf': [1, 2],
    'max_features': ['sqrt', 'log2']
}

grid_search = GridSearchCV(
    RandomForestRegressor(random_state=42),
    param_grid,
    cv=5,
    scoring='neg_mean_absolute_error',
    n_jobs=-1
)

grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_
```

## Appendix: Troubleshooting

| Issue | Solution |
|-------|----------|
| High false positives | Increase `error_threshold` (0.15 default), adjust `n_steps` window |
| Missing anomalies | Decrease threshold, improve model accuracy |
| Slow inference (>50ms) | Reduce trees, enable Intel optimizations, simpler model |
| Overfitting | Reduce `max_depth`, increase `min_samples_split`, more data |
| Poor generalization | Multi-turbine training data, feature engineering |

## Integration Checklist

- [ ] Model saved (.pkl, .onnx, .pt, etc.)
- [ ] `config.json` updated with model filename
- [ ] Model in `time-series-analytics-config/models/`
- [ ] UDF loading logic updated
- [ ] Prediction interface compatible
- [ ] Tested on target hardware
- [ ] Performance validated (latency, accuracy)
- [ ] Model version documented

---

## Appendix: References and Resources

### Documentation
- [Training README](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/training/README.md)
- [Application Config](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)
- [UDF Implementation](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/windturbine_anomaly_detector.py)

### Data Sources
- **Primary Dataset**: [Kaggle Wind Turbine SCADA Dataset](https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset)
- Training File: `training/T1.csv`
- Simulation File: `simulation-data/wind-turbine-anomaly-detection.csv`

### Tools and Libraries
- **Intel® Extension for Scikit-learn**: Performance optimization
- **Scikit-learn**: Model training and evaluation
- **Kapacitor**: Time series processing and UDF framework
- **Grafana**: Visualization dashboard

### Recommended Reading
- Wind Turbine Power Curve modeling techniques (Eg: https://www.mdpi.com/1996-1073/16/1/180)
- Edge AI deployment best practices
- Intel optimization guides for ML inference: https://www.intel.com/content/www/us/en/developer/tools/oneapi/scikit-learn.html
- Time series anomaly detection methods