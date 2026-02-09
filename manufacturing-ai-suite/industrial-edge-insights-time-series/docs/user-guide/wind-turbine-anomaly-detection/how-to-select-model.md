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
- **Input**: Wind Speed (m/s)
- **Output**: Expected Grid Active Power (kW)
- **Deployment**: Edge devices with GPU support
- **Framework**: Kapacitor UDF (User Defined Function)
- **Mode**: Single-point streaming inference
- **Latency**: < 10ms per prediction

---

## Reference Implementation

**Current Model**: Random Forest Regressor (350 trees, max_depth=25)
- **File**: `windturbine_anomaly_detector.pkl`
- **Performance**: MAE < 50 kW, R² > 0.95
- **Why**: Good balance of accuracy, speed, and interpretability

**You can replace this with any model** - see integration section below.

---

## Model Selection Criteria

| Criterion | Requirement | Target | Excellent |
|-----------|-------------|--------|----------|
| **MAE** | < 100 kW | < 50 kW | < 30 kW |
| **RMSE** | < 150 kW | < 100 kW | < 70 kW |
| **R² Score** | > 0.90 | > 0.95 | > 0.97 |
| **Inference Latency** | < 50ms | < 10ms | < 5ms |
| **Model Size** | < 100 MB | < 50 MB | < 20 MB |
| **Memory Usage** | < 1 GB | < 500 MB | < 200 MB |
| **False Positive Rate** | < 10% | < 5% | < 2% |
| **False Negative Rate** | < 5% | < 2% | < 1% |

**Additional Considerations**:
- Wind speed range: 3-14 m/s operational
- Training data: 10k-50k samples minimum
- Handle missing/NaN values
- Support single-point predictions
- Compatible with Python UDF framework

---

## Model Comparison

| Model | Accuracy | Speed | Size | GPU | Use Case |
|-------|----------|-------|------|-----|----------|
| **Random Forest** ⭐ | High | Medium | 5-20 MB | ❌ | **Balanced choice** - Current implementation |
| **XGBoost/LightGBM** | Highest | Fast | 5-30 MB | ✅ | Maximum accuracy with GPU |
| **Polynomial Reg** | Medium | Fastest | <1 MB | ❌ | Simple curves, minimal resources |
| **SVR** | Medium-High | Medium | 2-10 MB | ❌ | Limited data (<10k samples) |
| **Neural Networks** | Highest | Fast* | 10-50 MB | ✅ | Temporal patterns, large datasets |
| **Decision Tree** | Low-Medium | Fastest | <1 MB | ❌ | Baseline only (not production) |

*With GPU

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
def load_model(filename):
    # Pickle (default)
    import pickle
    return pickle.load(open(filename, 'rb'))
    
    # ONNX
    # import onnxruntime as rt
    # return rt.InferenceSession(filename)
    
    # PyTorch
    # model = YourModelClass()
    # model.load_state_dict(torch.load(filename))
    # return model.eval()

# 2. Update inference
y_pred = self.model.predict(np.reshape(x, (-1, 1)))  # sklearn
# y_pred = self.model.run(None, {'input': x})[0]  # ONNX
# y_pred = self.model(torch.tensor([[x]])).item()  # PyTorch
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

### Minimum Acceptable Performance

| Metric | Minimum | Target | Excellent |
|--------|---------|--------|-----------|
| MAE | < 100 kW | < 50 kW | < 30 kW |
| RMSE | < 150 kW | < 100 kW | < 70 kW |
| R² Score | > 0.90 | > 0.95 | > 0.97 |
| Inference Time | < 50ms | < 10ms | < 5ms |
| Model Size | < 100 MB | < 50 MB | < 20 MB |
| False Positive Rate | < 10% | < 5% | < 2% |
| False Negative Rate | < 5% | < 2% | < 1% |

### Performance Testing Protocol

1. **Split Data**: 70% train, 30% test
2. **Cross-Validation**: 5-fold CV on training set
3. **Test Set**: Never used during training/tuning
4. **Hardware Testing**: Profile on target edge device (both CPU and GPU)
5. **Load Testing**: Simulate 10+ concurrent turbine streams
6. **GPU Efficiency**: Measure GPU memory usage and utilization
7. **Batch vs Single**: Test both single-point and batch inference for GPU models

**GPU-Specific Tests**:
- Measure inference time with different batch sizes (1, 8, 16, 32)
- Monitor VRAM consumption
- Test CPU fallback behavior if GPU unavailable
- Benchmark against CPU baseline

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
    start = time.time()
    for _ in range(1000):
        model.predict(X_test[:1])
    print(f"Avg latency: {(time.time()-start):.2f} ms")
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

## Model Selection Decision Tree

Use this decision tree to select the appropriate model:

```
START
│
├─ Do you have <10,000 samples?
│  ├─ YES → Consider Polynomial Regression or SVR
│  └─ NO → Continue
│
├─ Is inference latency critical (<5ms)?
│  ├─ YES → Consider Polynomial Regression (degree 2-3)
│  └─ NO → Continue
│
├─ Do you need maximum accuracy (R² > 0.97)?
│  ├─ YES → Test options:
│  │        1. Gradient Boosting with GPU (LightGBM/XGBoost)
│  │        2. Neural Networks with GPU (if >50k samples)
│  └─ NO → Continue
│
├─ Do you want to capture temporal patterns?
│  ├─ YES → LSTM/Neural Network with GPU (needs >50k samples)
│  └─ NO → Continue
│
├─ Is model interpretability important?
│  ├─ YES → Random Forest (feature importance) or Polynomial
│  └─ NO → Continue
│
├─ Is model size constrained (<20 MB)?
│  ├─ YES → Polynomial Regression or optimized Random Forest
│  └─ NO → Continue
│
├─ Want to leverage GPU acceleration?
│  ├─ YES → Consider XGBoost/LightGBM with GPU or Neural Networks
│  └─ NO → Continue
│
└─ DEFAULT → Random Forest Regressor ✓ (Current Choice - Balanced)
              Alternative: XGBoost with GPU (Better accuracy)
```

**GPU-Enabled Quick Selection Guide**:
- **Best Accuracy + GPU**: Neural Network (LSTM/MLP) or XGBoost GPU
- **Best Balance**: Random Forest or LightGBM GPU  
- **Fastest Inference**: Polynomial Regression
- **Most Interpretable**: Random Forest or Polynomial
- **Temporal Patterns**: LSTM with GPU

---

## Appendix A: Hyperparameter Tuning Guidance

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

## Hyperparameter Tuning (Random Forest)

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [200, 350, 500],
    'max_depth': [20, 25, 30],
    'min_samples_split': [2, 5]
}

GridSearchCV(RandomForestRegressor(), param_grid, cv=5, 
             scoring='neg_mean_absolute_error').fit(X_train, y_train)
```

## Integration Checklist

- [ ] Model saved (.pkl, .onnx, .pt, etc.)
- [ ] `config.json` updated with model filename
- [ ] Model in `time-series-analytics-config/models/`
- [ ] UDF loading logic updated
- [ ] Prediction interface compatible
- [ ] Tested on target hardware
- [ ] Performance validated (latency, accuracy)
- [ ] Version documented

---

## Appendix D: References and Resources

### Documentation
- [Training README](training/README.md)
- [Application Config](time-series-analytics-config/config.json)
- [UDF Implementation](time-series-analytics-config/udfs/windturbine_anomaly_detector.py)

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
- Wind Turbine Power Curve modeling techniques
- Edge AI deployment best practices
- Intel optimization guides for ML inference
- Time series anomaly detection methods

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-09 | System | Initial model selection guidelines document |

---

## Contact and Support

For questions or updates to these guidelines, please refer to the project documentation or contact the development team.

**Last Updated**: February 9, 2026
