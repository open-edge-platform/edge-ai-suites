#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Weld Defect Inference Sample Script
=====================================
Demonstrates row-by-row model inference using the exported model artefacts.
Accepts input from:
  - A CSV file supplied on the command line (processed row by row)
  - Hard-coded demo rows (run with no arguments)

Intel Acceleration
------------------
Applies Intel Extension for Scikit-learn (scikit-learn-intelex) before the
model is loaded.  When running on an Intel CPU or iGPU this routes
RandomForestClassifier inference through the oneDAL backend automatically.
Falls back silently to standard scikit-learn if the package is unavailable.

Usage:
    # Demo mode (built-in sample rows)
    python weld_defect_inference_sample.py

    # CSV mode — runs inference row by row and prints results
    python weld_defect_inference_sample.py path/to/input.csv

    # CSV mode — write results to a new CSV
    python weld_defect_inference_sample.py path/to/input.csv --out results.csv

Required artefacts (produced by weld_defect_train.py):
    weld_defect_model.pkl
    weld_defect_labels.pkl
    model_info.json          (optional — used for metadata display)
"""

import sys
import json
import csv
import argparse
from pathlib import Path

# ── Intel Extension for Scikit-learn ─────────────────────────────────────────
# MUST be applied before joblib loads the pickled sklearn objects so that
# the deserialized estimator runs on the oneDAL / Intel iGPU backend.
try:
    from sklearnex import patch_sklearn
    patch_sklearn(verbose=False)
    _INTEL_PATCHED = True
except ImportError:
    _INTEL_PATCHED = False
# ─────────────────────────────────────────────────────────────────────────────

import joblib
import numpy as np

# ── Artefact paths ────────────────────────────────────────────────────────────
_BASE         = Path(__file__).parent
MODEL_PATH    = _BASE / "weld_anomaly_detector.pkl"
LABELS_PATH   = _BASE / "weld_anomaly_detector_labels.pkl"
INFO_PATH     = _BASE / "weld_anomaly_detector.json"

# Feature column names — must match training order exactly
FEATURES = [
    "Pressure",
    "CO2 Weld Flow",
    "Feed",
    "Primary Weld Current",
    "Secondary Weld Voltage",
]

GOOD_WELD_LABEL = "Good Weld"


def _build_explanation(input_row: dict, predicted_category: str, prob_map: dict, model_info: dict) -> dict:
    """Create a human-readable reason block for why a row was classified as a category."""
    stats = model_info.get("class_feature_stats", {}) if model_info else {}
    pred_stats = stats.get(predicted_category, {})
    good_stats = stats.get(GOOD_WELD_LABEL, {})

    # Sort probabilities and include top alternatives for context.
    ranked = sorted(prob_map.items(), key=lambda kv: kv[1], reverse=True)
    top_probs = [{"category": k, "probability": round(float(v), 6)} for k, v in ranked[:3]]

    signal_features = []
    for feat in FEATURES:
        if feat not in pred_stats or feat not in good_stats:
            continue
        value = float(input_row[feat])
        pred_mean = float(pred_stats[feat].get("mean", 0.0))
        pred_std = max(float(pred_stats[feat].get("std", 0.0)), 1e-6)
        good_mean = float(good_stats[feat].get("mean", 0.0))
        good_std = max(float(good_stats[feat].get("std", 0.0)), 1e-6)

        # Positive score means closer to predicted class profile than Good Weld profile.
        z_to_pred = abs(value - pred_mean) / pred_std
        z_to_good = abs(value - good_mean) / good_std
        evidence = z_to_good - z_to_pred

        signal_features.append(
            {
                "feature": feat,
                "value": round(value, 6),
                "predicted_mean": round(pred_mean, 6),
                "good_weld_mean": round(good_mean, 6),
                "evidence_score": round(float(evidence), 6),
            }
        )

    signal_features.sort(key=lambda x: x["evidence_score"], reverse=True)
    top_signals = signal_features[:3]

    if top_signals:
        reason = (
            f"Classified as {predicted_category} because key signals "
            f"({', '.join(s['feature'] for s in top_signals)}) align more with "
            f"{predicted_category} profile than Good Weld profile."
        )
    else:
        reason = (
            f"Classified as {predicted_category} based on model probability ranking; "
            "class profile statistics were not available."
        )

    return {
        "reason": reason,
        "top_probabilities": top_probs,
        "top_signal_features": top_signals,
    }


def configure_device(device: str):
    """Configure explicit Intel oneDAL offload target when sklearnex is present."""
    if device == "auto":
        return "auto"

    if not _INTEL_PATCHED:
        print(
            "Requested device selection but scikit-learn-intelex is not installed; "
            "continuing with standard sklearn on CPU."
        )
        return "cpu"

    try:
        import onedal
        # target_offload requires DPC++ oneDAL backend. Host-only builds cannot offload.
        if getattr(onedal, "_dpc_backend", None) is None:
            print(
                "Requested device offload but this oneDAL build is host-only "
                "(no DPC backend). Falling back to host CPU."
            )
            return "host-cpu"
    except Exception:
        # If backend introspection fails, continue and let set_config decide.
        pass

    from sklearnex import set_config
    target = "cpu" if device == "cpu" else "gpu:0"
    set_config(target_offload=target)
    return target


# ── Model loader ──────────────────────────────────────────────────────────────

def load_model():
    """Load the pipeline and label encoder from disk (once at startup)."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}\n"
            "Run  python weld_defect_train.py  first."
        )
    pipeline = joblib.load(MODEL_PATH)
    le       = joblib.load(LABELS_PATH)
    return pipeline, le


# ── Core inference function ───────────────────────────────────────────────────

def predict_row(pipeline, le, pressure, co2_weld_flow, feed,
                primary_weld_current, secondary_weld_voltage, model_info=None) -> dict:
    """
    Run inference on a single sensor reading.

    Parameters
    ----------
    pipeline              : loaded sklearn Pipeline
    le                    : fitted LabelEncoder
    pressure              : float
    co2_weld_flow         : float
    feed                  : float
    primary_weld_current  : float
    secondary_weld_voltage: float

    Returns
    -------
    dict
        predicted_category  — defect class name (str)
        is_defect           — True unless predicted class is Good Weld (bool)
        defect_probability  — 1 − P(Good Weld) (float 0–1)
        good_weld_probability — P(Good Weld) (float 0–1)
        confidence          — probability of the predicted class (float 0–1)
        probabilities       — {class_name: probability, ...} for all 12 classes
    """
    x = np.array(
        [[pressure, co2_weld_flow, feed, primary_weld_current, secondary_weld_voltage]],
        dtype=np.float32,
    )

    pred_idx   = pipeline.predict(x)[0]
    pred_proba = pipeline.predict_proba(x)[0]

    classes             = list(le.classes_)
    predicted_category  = le.inverse_transform([pred_idx])[0]
    prob_map            = {cls: round(float(p), 6) for cls, p in zip(classes, pred_proba)}

    good_weld_prob = prob_map.get(GOOD_WELD_LABEL, 0.0)
    confidence     = round(float(pred_proba[pred_idx]), 6)

    input_row = {
        "Pressure": pressure,
        "CO2 Weld Flow": co2_weld_flow,
        "Feed": feed,
        "Primary Weld Current": primary_weld_current,
        "Secondary Weld Voltage": secondary_weld_voltage,
    }
    explanation = _build_explanation(input_row, predicted_category, prob_map, model_info or {})

    return {
        "predicted_category":   predicted_category,
        "is_defect":            predicted_category != GOOD_WELD_LABEL,
        "defect_probability":   round(1.0 - good_weld_prob, 6),
        "good_weld_probability": round(good_weld_prob, 6),
        "confidence":           confidence,
        "probabilities":        prob_map,
        "explanation":          explanation,
    }


# ── CSV row-by-row processing ────────────────────────────────────────────────

def run_csv(pipeline, le, input_path: Path, output_path=None, model_info=None):
    """Read a CSV row by row, run inference, and print / save results."""
    import pandas as pd

    df = pd.read_csv(input_path)
    df.columns = df.columns.str.strip()

    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        raise ValueError(
            f"Input CSV is missing required columns: {missing}\n"
            f"Required: {FEATURES}"
        )

    print(f"\nProcessing {len(df):,} rows from  {input_path.name}\n")
    print(f"{'Row':>5}  {'Predicted Category':<38}  {'is_defect':<10}  "
          f"{'Defect Prob':>11}  {'Confidence':>10}")
    print("-" * 85)

    results = []
    for i, row in df[FEATURES].iterrows():
        result = predict_row(pipeline, le, *row.values, model_info=model_info)
        results.append(result)

        flag = "DEFECT" if result["is_defect"] else "OK    "
        print(
            f"{i+1:>5}  {result['predicted_category']:<38}  {flag:<10}  "
            f"{result['defect_probability']:>11.4f}  {result['confidence']:>10.4f}"
        )

    if output_path:
        out_df = df.copy()
        out_df["predicted_category"]    = [r["predicted_category"]    for r in results]
        out_df["is_defect"]             = [r["is_defect"]             for r in results]
        out_df["defect_probability"]    = [r["defect_probability"]    for r in results]
        out_df["good_weld_probability"] = [r["good_weld_probability"] for r in results]
        out_df["confidence"]            = [r["confidence"]            for r in results]
        out_df["reason"]                = [r["explanation"]["reason"] for r in results]
        out_df.to_csv(output_path, index=False)
        print(f"\nResults saved → {output_path}")

    # Summary
    defect_count = sum(1 for r in results if r["is_defect"])
    print(f"\nSummary: {defect_count}/{len(results)} rows classified as defect "
          f"({100*defect_count/len(results):.1f}%)")


# ── Demo mode (hard-coded representative rows) ───────────────────────────────

DEMO_ROWS = [
    # label,                          Pressure  CO2   Feed   Current  Voltage
    ("Excessive Penetration sample",   2.91,    0.0,  6.07,  0.0,     81.91),
    ("Good Weld sample",               1.56,   -0.11, 0.0,   0.0,     0.0  ),
    ("Burnthrough Weld sample",        3.40,    5.50, 48.52, 182.34,  28.11),
    ("Crater Cracks sample",           2.01,   14.25, 2.62,  291.73,  40.23),
    ("Undercut high-feed sample",      3.36,   35.85, 175.12,343.75,  40.23),
    ("Overlap low-feed sample",        1.95,   10.20, 1.31,  254.73,  40.23),
]

def run_demo(pipeline, le, model_info=None):
    print(f"\n{'Sample Label':<34}  {'Predicted Category':<38}  "
          f"{'is_defect':<10}  {'Defect Prob':>11}  {'Confidence':>10}")
    print("-" * 105)

    for label, pr, co2, fd, cur, volt in DEMO_ROWS:
        r = predict_row(pipeline, le, pr, co2, fd, cur, volt, model_info=model_info)
        flag = "DEFECT" if r["is_defect"] else "OK    "
        print(
            f"{label:<34}  {r['predicted_category']:<38}  {flag:<10}  "
            f"{r['defect_probability']:>11.4f}  {r['confidence']:>10.4f}"
        )

    # Show one full JSON output
    print("\n── Full JSON output for first demo row ──────────────────────────────")
    import json
    _, pr, co2, fd, cur, volt = DEMO_ROWS[0]
    print(json.dumps(predict_row(pipeline, le, pr, co2, fd, cur, volt, model_info=model_info), indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Weld defect inference — row-by-row prediction"
    )
    parser.add_argument(
        "input_csv", nargs="?", default=None,
        help="Path to input CSV with sensor columns (optional; runs demo if omitted)"
    )
    parser.add_argument(
        "--out", default=None,
        help="Save annotated results to this CSV file"
    )
    parser.add_argument(
        "--device", choices=["auto", "cpu", "gpu"], default="gpu",
        help="Inference device target for Intel backend: auto, cpu, gpu"
    )
    args = parser.parse_args()

    selected_target = configure_device(args.device)

    # Display Intel status
    print("=" * 60)
    print(" WELD DEFECT INFERENCE")
    print("=" * 60)
    if _INTEL_PATCHED:
        print("Intel Extension for Scikit-learn: ENABLED  (oneDAL / Intel iGPU backend)")
    else:
        print("Intel Extension for Scikit-learn: NOT available (standard sklearn)")
    print(f"Requested device: {args.device}")
    print(f"Active target   : {selected_target}")

    # Show model metadata if available
    info = {}
    if INFO_PATH.exists():
        info = json.loads(INFO_PATH.read_text())
        print(f"Model           : {info.get('algorithm', 'unknown')}")
        print(f"Trained at      : {info.get('trained_at', 'unknown')}")
        print(f"Classes         : {len(info.get('classes', []))}")
        print(f"Trained w/ Intel: {info.get('intel_patched', 'unknown')}")

    print()

    # Load model artefacts
    pipeline, le = load_model()
    print(f"Model loaded from {MODEL_PATH.name}")

    if args.input_csv:
        run_csv(pipeline, le, Path(args.input_csv),
                Path(args.out) if args.out else None, model_info=info)
    else:
        print("\nNo input CSV provided — running built-in demo rows.")
        run_demo(pipeline, le, model_info=info)


if __name__ == "__main__":
    main()
