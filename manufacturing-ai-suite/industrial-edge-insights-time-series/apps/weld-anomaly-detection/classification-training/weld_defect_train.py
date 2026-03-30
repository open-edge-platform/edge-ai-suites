"""
Weld Defect Multi-Class Classifier — Training Script
=====================================================
Features  : Pressure, CO2 Weld Flow, Feed, Primary Weld Current,
            Secondary Weld Voltage
Target    : Defect category (12 classes)
Outputs   :
  - weld_defect_model.pkl   — trained pipeline (scaler + classifier)
  - weld_defect_labels.pkl  — label-encoder mapping
  - weld_defect_report.txt  — classification report + cross-val scores
  - model_info.json         — metadata consumed by inference scripts

Intel Acceleration
------------------
Uses Intel Extension for Scikit-learn (scikit-learn-intelex) which patches
supported estimators (RandomForestClassifier, StandardScaler, train_test_split,
etc.) to run via oneDAL, enabling acceleration on Intel CPUs and iGPUs.
Falls back silently to standard scikit-learn if the package is not installed.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# ── Intel Extension for Scikit-learn — must be applied BEFORE sklearn imports ──
try:
    from sklearnex import patch_sklearn
    patch_sklearn(verbose=False)          # patches RandomForestClassifier, StandardScaler, etc.
    _INTEL_PATCHED = True
except ImportError:
    _INTEL_PATCHED = False

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

# ── Configuration ─────────────────────────────────────────────────────────────

DATA_DIR = Path(
    "edge-ai-suites/manufacturing-ai-suite/"
    "industrial-edge-insights-multimodal/"
    "weld-data-simulator/simulation-data"
)

FEATURES = [
    "Pressure",
    "CO2 Weld Flow",
    "Feed",
    "Primary Weld Current",
    "Secondary Weld Voltage",
]

MODEL_OUT   = Path("weld_defect_model.pkl")
LABELS_OUT  = Path("weld_defect_labels.pkl")
REPORT_OUT  = Path("weld_defect_report.txt")

CATEGORY_LABELS = {
    "burnthrough_weld_12-14-22-0201-02":              "Burnthrough Weld",
    "crater_cracks_03-20-23-0122-11":                 "Crater Cracks",
    "excessive_convexity_03-04-23-0001-08":           "Excessive Convexity",
    "excessive_penetration_02-19-23-0041-01":         "Excessive Penetration",
    "good_weld_02-16-23-0081-00":                     "Good Weld",
    "lack_of_fusion_11-21-22-0161-07":                "Lack of Fusion",
    "overlap_03-22-23-0041-06":                       "Overlap",
    "porosity_w_ep_02-26-23-0101-04":                 "Porosity w/ EP",
    "porosity_w-excessive_penetration_11-01-22-0161-04": "Porosity w/ Excessive Penetration",
    "spatter_12-31-22-0001-09":                       "Spatter",
    "undercut_03-15-23-0081-05":                      "Undercut",
    "warping_weld_11-09-22-0041-10":                  "Warping Weld",
}

# ── Data Loading ───────────────────────────────────────────────────────────────

def load_data(data_dir: Path) -> pd.DataFrame:
    frames = []
    for csv_file in sorted(data_dir.glob("*.csv")):
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip()
        stem = csv_file.stem
        df["category"] = CATEGORY_LABELS.get(stem, stem)
        frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    data = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(data):,} rows across {data['category'].nunique()} categories")
    return data


def preprocess(data: pd.DataFrame):
    # Drop rows with NaN in any feature column
    data = data.dropna(subset=FEATURES + ["category"]).copy()

    X = data[FEATURES].values.astype(np.float32)
    y_raw = data["category"].values

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    return X, y, le


# ── Model Definition ───────────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    """
    StandardScaler normalises features, then RandomForestClassifier handles
    the multi-class problem.

    RandomForestClassifier is accelerated by Intel Extension for Scikit-learn
    (oneDAL backend) on Intel CPUs and iGPUs — unlike GradientBoostingClassifier
    which is not in the Intel patch map.
    """
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=42,
    )
    return Pipeline([("scaler", StandardScaler()), ("clf", clf)])


# ── Training & Evaluation ──────────────────────────────────────────────────────

def train_and_evaluate(X, y, le: LabelEncoder) -> Pipeline:
    class_names = le.classes_

    # ── Cross-validation (stratified 5-fold) ──────────────────────────────────
    print("\n[1/3] Running 5-fold stratified cross-validation …")
    pipeline = build_pipeline()
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipeline, X, y, cv=skf, scoring="accuracy", n_jobs=-1)
    print(f"      CV Accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"      Per-fold  : {np.round(cv_scores, 4)}")

    # ── Hold-out evaluation ───────────────────────────────────────────────────
    print("\n[2/3] Training on 80 % hold-out split for detailed report …")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)

    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=class_names, digits=4)
    cm = confusion_matrix(y_test, y_pred)

    print(f"      Hold-out Accuracy: {acc:.4f}")
    print("\nClassification Report:\n")
    print(report)

    # Write report to file
    with open(REPORT_OUT, "w") as f:
        f.write("WELD DEFECT CLASSIFIER — EVALUATION REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"CV Accuracy (5-fold): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}\n")
        f.write(f"Hold-out Accuracy   : {acc:.4f}\n\n")
        f.write("Classification Report (hold-out):\n")
        f.write(report + "\n\n")
        f.write("Confusion Matrix (rows=actual, cols=predicted):\n")
        f.write("Labels: " + ", ".join(class_names) + "\n")
        f.write(np.array2string(cm) + "\n")
    print(f"      Report saved → {REPORT_OUT}")

    # ── Final model: retrain on ALL data ─────────────────────────────────────
    print("\n[3/3] Retraining on full dataset …")
    final_pipeline = build_pipeline()
    final_pipeline.fit(X, y)
    return final_pipeline


# ── Save Artefacts ─────────────────────────────────────────────────────────────

MODEL_INFO_OUT = Path("model_info.json")

def save_artefacts(pipeline: Pipeline, le: LabelEncoder):
    import datetime

    joblib.dump(pipeline, MODEL_OUT)
    joblib.dump(le,       LABELS_OUT)

    # Human-readable model metadata — used by inference scripts
    model_info = {
        "model_file":    str(MODEL_OUT),
        "labels_file":   str(LABELS_OUT),
        "features":      FEATURES,
        "classes":       list(le.classes_),
        "good_weld_label": "Good Weld",
        "trained_at":    datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "algorithm":     "RandomForestClassifier",
        "intel_patched": _INTEL_PATCHED,
        "note": (
            "Load model with joblib.load(model_file). "
            "Input shape: (N, 5) — columns must follow 'features' order exactly. "
            "Apply sklearnex.patch_sklearn() before loading for Intel iGPU acceleration."
        ),
    }
    with open(MODEL_INFO_OUT, "w") as f:
        json.dump(model_info, f, indent=2)

    print(f"\nModel      saved → {MODEL_OUT}")
    print(f"Labels     saved → {LABELS_OUT}")
    print(f"Model info saved → {MODEL_INFO_OUT}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(" WELD DEFECT CLASSIFIER — TRAINING")
    print("=" * 60)
    if _INTEL_PATCHED:
        print("Intel Extension for Scikit-learn: ENABLED (oneDAL backend)")
    else:
        print("Intel Extension for Scikit-learn: NOT available (using standard sklearn)")

    data = load_data(DATA_DIR)

    print("\nSamples per category:")
    for cat, cnt in data["category"].value_counts().items():
        print(f"  {cat:<45} {cnt:>5}")

    X, y, le = preprocess(data)
    print(f"\nFeatures : {FEATURES}")
    print(f"Classes  : {list(le.classes_)}")

    pipeline = train_and_evaluate(X, y, le)
    save_artefacts(pipeline, le)

    print("\nDone. Use weld_defect_predict.py for row-by-row inference.")


if __name__ == "__main__":
    main()
