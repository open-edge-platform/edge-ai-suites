# Wind Turbine Anomaly Detection: Approach Comparison

## Original Notebook Approach (High Variance)

### Model Training
- **RandomForest**: 350 trees, max_depth=25 (unlimited growth)
- **Data**: wind_speed vs Theoretical_Power_Curve (clean, idealized data)
- **Issue**: Overfits to theoretical curve, high variance on real field data

### Anomaly Detection Logic
1. **Error computation**: `error = (y_pred - y) / y` (relative error)
   - Unstable when actual power ≈ 0
   - Magnifies small errors

2. **Sliding window validation** (3 consecutive points):
   - Flags point if error > 15% threshold
   - Only confirms if window is fully anomalous (all 3 points flagged)

3. **LinearRegression validation** (THE PROBLEM):
   - Fits LR to captured window points
   - Uses magic threshold: `|LR_coefficient| < 200`
   - Arbitrary, heuristic-based, data-dependent
   - Causes false positives/negatives

4. **Severity classification** (error-based):
   - LOW: error < 30%
   - MEDIUM: error < 60%
   - HIGH: error > 60%

### Problems
- ❌ Overfitted model → high variance
- ❌ LinearRegression validation → unreliable
- ❌ Magic threshold (< 200) → not generalizable
- ❌ Sliding window → misses isolated anomalies
- ❌ Relative error → unstable with near-zero actuals

---

## New Approach (Optimized, Low Variance)

### Model Training
- **RandomForest**: 50 trees, max_depth=15 (regularized)
- **Data**: wind_speed only (simpler, more robust)
- **Advantage**: Lower variance, generalizes better to field data

### Anomaly Detection Logic (NO LinearRegression)
1. **Residual computation**: `residual = actual - predicted` (absolute, stable)
   - Works with any actual power value
   - Direct deviation measurement

2. **Percentile-based thresholding** (statistical, data-driven):
   - MEDIUM threshold: 75th percentile of |residuals|
   - HIGH threshold: 95th percentile of |residuals|
   - Automatically adapts to data distribution

3. **Row-by-row processing**:
   - No sliding window → catches isolated anomalies
   - Each row scored independently

4. **Severity classification** (percentile-based):
   - NORMAL: residual ≤ p75
   - MEDIUM: p75 < residual ≤ p95
   - HIGH: residual > p95

### Advantages
- ✅ Regularized model → low variance
- ✅ NO LinearRegression → simpler, deterministic
- ✅ Data-driven thresholds → adaptive
- ✅ Row-by-row → catches all anomalies
- ✅ Absolute residuals → stable, interpretable

---

## Quantitative Comparison

### Model Sizes
| Metric | Original | New (Compact) |
|--------|----------|---------------|
| Trees | 350 | 50 |
| Max Depth | Unlimited (25+) | 15 |
| File Size | 7.4 MB | 1.3 MB |
| R² Score | 0.9063 | 0.9062 |
| RMSE | 399.88 | 400.01 |

**Result**: New model is 82.4% smaller with virtually identical accuracy

### Anomaly Detection
| Metric | Original (field data) | New (simulation data) |
|--------|--------|---------|
| Processing | Sliding window + LR validation | Row-by-row percentile |
| NORMAL samples | ~75% | 2,607 (75.0%) |
| MEDIUM anomalies | ~20% | 697 (20.1%) |
| HIGH anomalies | ~5% | 172 (4.9%) |
| Hidden parameters | >5 (cut_in, cut_out, error_threshold, LR coef, window size) | 2 (percentile values: 75, 95) |

**Result**: New approach has fewer hidden parameters, more transparent thresholds

---

## Why LinearRegression Causes High Variance

The original approach uses LinearRegression to "validate" detected anomalies:

```python
lm = LinearRegression()
lm.fit(x_feat, y_feat)  # x_feat: 3 wind speeds, y_feat: 3 actual powers
if abs(lm.coef_) < 200:  # Magic threshold!
    mark_as_anomaly()
```

**Problems**:
1. Fitting LR to only 3 points → huge variance
2. Coefficient is sensitive to scale and data range
3. Threshold 200 is not justified (why 200? why not 150 or 250?)
4. Falls back to error-based heuristics when LR fails

---

## Recommendation

**Use the new approach** because:
1. ✅ No linear regression → eliminating a major source of variance
2. ✅ Percentile-based thresholds → statistically sound, self-adapting
3. ✅ Simpler model → easier to maintain and debug
4. ✅ Better generalization → works on unseen data
5. ✅ Explicit float32 → consistent precision
6. ✅ GPU-accelerated → Intel sklearnex integration

**For even better results**, consider:
- Using only MEDIUM + HIGH (exclude NORMAL from alerts)
- Adjusting percentiles (e.g., 80/95 instead of 75/95) based on domain needs
- Adding temporal smoothing (moving average of residuals)
- Ensemble with Isolation Forest for additional robustness
