"""
Weld Defect Multi-Class Classifier - Training Script
====================================================
Features  : Pressure, CO2 Weld Flow, Feed, Primary Weld Current,
            Secondary Weld Voltage
Target    : Defect category (12 classes)
Outputs   :
  - weld_defect_model.pkl   - trained pipeline (scaler + classifier)
  - weld_defect_labels.pkl  - label-encoder mapping
  - weld_defect_report.txt  - classification report on VAL split
  - model_info.json         - metadata consumed by inference scripts

Intel Acceleration
------------------
Uses Intel Extension for Scikit-learn (scikit-learn-intelex) which patches
supported estimators (RandomForestClassifier, StandardScaler, etc.) to run via
oneDAL, enabling acceleration on Intel CPUs and iGPUs.
Falls back silently to standard scikit-learn if the package is not installed.
"""

import json
import os
import re
import glob
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# -- Intel Extension for Scikit-learn: patch BEFORE sklearn imports --
try:
    from sklearnex import patch_sklearn
    patch_sklearn(verbose=False)
    _INTEL_PATCHED = True
except ImportError:
    _INTEL_PATCHED = False

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

# -- Configuration -------------------------------------------------------------

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/welding_dataset"))
MANIFEST_NAME = "manifest.csv"
TARGET_STEEL_TYPE = "FE410"
MIN_WELD_CURRENT = 50.0

FEATURES = [
    "Pressure",
    "CO2 Weld Flow",
    "Feed",
    "Primary Weld Current",
    "Secondary Weld Voltage",
]

MODEL_OUT = Path("weld_defect_model.pkl")
LABELS_OUT = Path("weld_defect_labels.pkl")
REPORT_OUT = Path("weld_defect_report.txt")
MODEL_INFO_OUT = Path("model_info.json")

CATEGORY_LABELS = {
    "burnthrough_weld_12-14-22-0201-02": "Burnthrough Weld",
    "crater_cracks_03-20-23-0122-11": "Crater Cracks",
    "excessive_convexity_03-04-23-0001-08": "Excessive Convexity",
    "excessive_penetration_02-19-23-0041-01": "Excessive Penetration",
    "good_weld_02-16-23-0081-00": "Good Weld",
    "lack_of_fusion_11-21-22-0161-07": "Lack of Fusion",
    "overlap_03-22-23-0041-06": "Overlap",
    "porosity_w_ep_02-26-23-0101-04": "Porosity w/ EP",
    "porosity_w-excessive_penetration_11-01-22-0161-04": "Porosity w/ Excessive Penetration",
    "spatter_12-31-22-0001-09": "Spatter",
    "undercut_03-15-23-0081-05": "Undercut",
    "warping_weld_11-09-22-0041-10": "Warping Weld",
}


# -- Manifest/Data Loading -----------------------------------------------------

def _normalize_col_name(name: str) -> str:
    return str(name).strip().upper().replace(" ", "_")


def _find_column(columns, candidates, required=True):
    lookup = {_normalize_col_name(c): c for c in columns}
    for candidate in candidates:
        key = _normalize_col_name(candidate)
        if key in lookup:
            return lookup[key]
    if required:
        raise KeyError(f"Missing required manifest column. Tried: {candidates}")
    return None


def _canonical_token(value) -> str:
    return "".join(ch for ch in str(value).strip().upper() if ch.isalnum())


def _normalize_category_label(raw_label, fallback_stem: str) -> str:
    if raw_label is not None:
        label = str(raw_label).strip()
        if label and label.upper() not in {"NAN", "NONE", "NULL"}:
            token = _canonical_token(label)
            if token in {"GOOD", "GOODWELD"}:
                return "Good Weld"
            return label

    return CATEGORY_LABELS.get(fallback_stem, fallback_stem)


def _normalize_split(value: str):
    token = _canonical_token(value)
    if not token:
        return None
    if "TRAIN" in token or token == "TRN":
        return "TRAIN"
    if "TEST" in token or token == "TST":
        return "TEST"
    if "VAL" in token or "VALID" in token or token == "DEV":
        return "VAL"
    return None


def _subdir_candidates(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return [""]
    raw = str(value).strip()
    if not raw or raw.upper() in {"NAN", "NONE", "NULL"}:
        return [""]

    parts = [p.strip() for p in re.split(r"[;,|]", raw) if p.strip()]
    return parts or [""]


def _resolve_manifest_paths(data_dir: Path, directory_value: str, subdir_value: str):
    directory_path = Path(directory_value).expanduser()
    candidates = []

    if directory_path.is_absolute():
        candidates.append(directory_path)
    else:
        candidates.append((data_dir / directory_path).resolve())
        candidates.append((data_dir.parent / directory_path).resolve())

    resolved = []
    seen = set()
    for base in candidates:
        full = (base / subdir_value).resolve() if subdir_value else base.resolve()
        key = str(full)
        if key not in seen:
            resolved.append(full)
            seen.add(key)
    return resolved


def _collect_csv_files(path: Path):
    if path.is_file() and path.suffix.lower() == ".csv":
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.csv"))
    return []


def _read_labeled_csv(csv_file: Path, split_name: str, category_label=None) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    stem = csv_file.stem
    df["category"] = _normalize_category_label(category_label, stem)
    df["split"] = split_name
    df["source_csv"] = str(csv_file)
    return df


def load_data_from_manifest(data_dir: Path, steel_type: str = TARGET_STEEL_TYPE):
    manifest_path = data_dir / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    manifest = pd.read_csv(manifest_path)
    if manifest.empty:
        raise ValueError(f"Manifest is empty: {manifest_path}")

    subdir_col = _find_column(
        manifest.columns,
        ["SUBDIRS", "SUBDIR", "SUB_DIR", "SUBDIRECTORY", "SUBDIRECTORIES", "PATH"],
        required=False,
    )
    dir_col = _find_column(
        manifest.columns,
        ["DIRECTORY", "DIR", "DATA_DIR", "FOLDER"],
        required=False,
    )
    split_col = _find_column(manifest.columns, ["SPLIT", "SET", "DATASET", "SUBSET"])
    category_col = _find_column(
        manifest.columns,
        ["CATEGORY", "CLASS", "LABEL", "TARGET", "DEFECT"],
        required=False,
    )
    steel_col = _find_column(
        manifest.columns,
        ["STEEL_TYPE", "STEEL", "MATERIAL", "MATERIAL_TYPE", "GRADE"],
    )

    target_steel = _canonical_token(steel_type)
    steel_mask = manifest[steel_col].map(_canonical_token) == target_steel
    filtered = manifest[steel_mask].copy()
    if filtered.empty:
        raise ValueError(
            f"No rows found in {manifest_path} for {steel_col} == '{steel_type}'."
        )

    split_frames = {"TRAIN": [], "TEST": [], "VAL": []}
    split_row_counts = {"TRAIN": 0, "TEST": 0, "VAL": 0}
    unresolved_rows = []
    total_resolved_files = 0

    def _as_existing_folder(raw_value):
        folder = str(raw_value).strip()
        if not folder or folder.upper() in {"NAN", "NONE", "NULL"}:
            return None

        # Same pattern as test.py: SUBDIRS are relative to data_dir unless absolute.
        path = Path(folder).expanduser()
        if not path.is_absolute():
            path = (data_dir / folder).resolve()
        else:
            path = path.resolve()

        return path if path.exists() else None

    for _, row in filtered.iterrows():
        split_name = _normalize_split(row[split_col])
        if split_name not in split_frames:
            continue
        split_row_counts[split_name] += 1

        row_folder_candidates = []
        attempted_paths = []

        # Prefer SUBDIRS-based loading to mirror test.py behavior.
        if subdir_col:
            for subdir_value in _subdir_candidates(row[subdir_col]):
                folder = _as_existing_folder(subdir_value)
                if folder is not None:
                    row_folder_candidates.append(folder)
                else:
                    attempted_paths.append(str((data_dir / str(subdir_value)).resolve()))

        # Fallback: DIRECTORY + optional SUBDIRS if present.
        if not row_folder_candidates and dir_col:
            directory_value = str(row[dir_col]).strip()
            if directory_value:
                if subdir_col:
                    for subdir_value in _subdir_candidates(row[subdir_col]):
                        for candidate_path in _resolve_manifest_paths(data_dir, directory_value, subdir_value):
                            attempted_paths.append(str(candidate_path))
                            if candidate_path.exists():
                                row_folder_candidates.append(candidate_path)
                else:
                    for candidate_path in _resolve_manifest_paths(data_dir, directory_value, ""):
                        attempted_paths.append(str(candidate_path))
                        if candidate_path.exists():
                            row_folder_candidates.append(candidate_path)

        row_csv_files = []
        for folder in row_folder_candidates:
            csv_files = sorted(glob.glob(str(folder / "*.csv")))
            if len(csv_files) == 1:
                row_csv_files.extend([Path(csv_files[0])])
            elif len(csv_files) > 1:
                # Keep strict row semantics from test.py: one CSV file per manifest row folder.
                raise ValueError(
                    f"Expected exactly 1 CSV under {folder}, found {len(csv_files)}"
                )

        if not row_csv_files:
            unresolved_rows.append(
                {
                    "split": split_name,
                    "directory": "" if not dir_col else str(row[dir_col]),
                    "subdirs": "" if not subdir_col else str(row[subdir_col]),
                    "attempted": attempted_paths[:4],
                }
            )
            continue

        # De-duplicate files in case multiple candidate paths resolve to the same file.
        seen_files = set()
        deduped_files = []
        for csv_file in row_csv_files:
            key = str(csv_file.resolve())
            if key not in seen_files:
                deduped_files.append(csv_file)
                seen_files.add(key)

        row_category = row[category_col] if category_col else None
        for csv_file in deduped_files:
            split_frames[split_name].append(
                _read_labeled_csv(csv_file, split_name, row_category)
            )
            total_resolved_files += 1

    if not split_frames["TRAIN"]:
        raw_splits = sorted(filtered[split_col].astype(str).dropna().unique().tolist())
        sample_unresolved = unresolved_rows[:5]
        raise ValueError(
            "No TRAIN data files resolved from manifest for FE410. "
            f"Rows by split after normalization: {split_row_counts}. "
            f"Raw split values in filtered manifest: {raw_splits}. "
            f"Sample unresolved rows: {sample_unresolved}"
        )
    if not split_frames["VAL"]:
        raise ValueError("No VAL data files resolved from manifest for FE410.")

    train_test_frames = split_frames["TRAIN"] + split_frames["TEST"]
    train_test_data = pd.concat(train_test_frames, ignore_index=True)
    val_data = pd.concat(split_frames["VAL"], ignore_index=True)

    print(
        "Loaded manifest data "
        f"(files={total_resolved_files}, train+test_rows={len(train_test_data):,}, val_rows={len(val_data):,})"
    )

    return train_test_data, val_data


def _clean_category_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["category"] = out["category"].astype(str).str.strip()
    out = out[out["category"] != ""].copy()
    out = out[out["category"].str.upper() != "NAN"].copy()
    return out


def preprocess_split_data(train_test_data: pd.DataFrame, val_data: pd.DataFrame):
    train_test_clean = train_test_data.dropna(subset=FEATURES + ["category"]).copy()
    val_clean = val_data.dropna(subset=FEATURES + ["category"]).copy()

    train_test_clean = _clean_category_column(train_test_clean)
    val_clean = _clean_category_column(val_clean)

    # Remove non-welding rows where primary current is below threshold.
    train_test_clean = train_test_clean[
        train_test_clean["Primary Weld Current"] >= MIN_WELD_CURRENT
    ].copy()
    val_clean = val_clean[
        val_clean["Primary Weld Current"] >= MIN_WELD_CURRENT
    ].copy()

    if train_test_clean.empty:
        raise ValueError(
            f"No training rows left after filtering Primary Weld Current >= {MIN_WELD_CURRENT}."
        )

    le = LabelEncoder()
    y_train = le.fit_transform(train_test_clean["category"].values)

    train_classes = set(le.classes_)
    val_classes = set(val_clean["category"].unique())
    unseen_in_train = sorted(val_classes - train_classes)
    if unseen_in_train:
        preview = ", ".join([repr(x) for x in unseen_in_train[:6]])
        print(
            "Warning: dropping VAL rows with classes not present in TRAIN/TEST: "
            f"{preview}"
        )
        val_clean = val_clean[val_clean["category"].isin(train_classes)].copy()

    if val_clean.empty:
        raise ValueError(
            "No evaluable VAL rows left after filtering classes to TRAIN/TEST overlap "
            f"and Primary Weld Current >= {MIN_WELD_CURRENT}."
        )

    val_index = pd.Index(le.classes_)
    y_val = val_index.get_indexer(val_clean["category"].values)

    X_train = train_test_clean[FEATURES].values.astype(np.float32)
    X_val = val_clean[FEATURES].values.astype(np.float32)

    return X_train, y_train, X_val, y_val, le, train_test_clean


# -- Model Definition ----------------------------------------------------------

def build_pipeline() -> Pipeline:
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=42,
    )
    return Pipeline([("scaler", StandardScaler()), ("clf", clf)])


# -- Training & Evaluation -----------------------------------------------------

def train_and_evaluate(X_train, y_train, X_val, y_val, le: LabelEncoder) -> Pipeline:
    class_names = list(le.classes_)

    print("Training model...")
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    print("Evaluating on VAL...")
    y_pred = pipeline.predict(X_val)

    acc = accuracy_score(y_val, y_pred)
    report = classification_report(y_val, y_pred, target_names=class_names, digits=4)
    cm = confusion_matrix(y_val, y_pred)

    print(f"VAL Accuracy: {acc:.4f}")

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("WELD DEFECT CLASSIFIER - EVALUATION REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write("Training split : TRAIN + TEST\n")
        f.write("Evaluation split: VAL\n")
        f.write(f"VAL Accuracy   : {acc:.4f}\n\n")
        f.write("Classification Report (VAL):\n")
        f.write(report + "\n\n")
        f.write("Confusion Matrix (rows=actual, cols=predicted):\n")
        f.write("Labels: " + ", ".join(class_names) + "\n")
        f.write(np.array2string(cm) + "\n")
    print(f"Saved report: {REPORT_OUT}")

    return pipeline


# -- Save Artifacts ------------------------------------------------------------

def _build_class_feature_stats(data: pd.DataFrame) -> dict:
    clean = data.dropna(subset=FEATURES + ["category"]).copy()
    stats = {}
    for category, grp in clean.groupby("category"):
        feat_stats = {}
        for feat in FEATURES:
            mean_val = float(grp[feat].mean())
            std_val = float(grp[feat].std()) if len(grp) > 1 else 0.0
            feat_stats[feat] = {
                "mean": round(mean_val, 6),
                "std": round(std_val if not np.isnan(std_val) else 0.0, 6),
            }
        stats[str(category)] = feat_stats
    return stats


def save_artefacts(pipeline: Pipeline, le: LabelEncoder, train_test_data: pd.DataFrame):
    import datetime

    joblib.dump(pipeline, MODEL_OUT)
    joblib.dump(le, LABELS_OUT)

    model_info = {
        "model_file": str(MODEL_OUT),
        "labels_file": str(LABELS_OUT),
        "features": FEATURES,
        "classes": list(le.classes_),
        "good_weld_label": "Good Weld",
        "class_feature_stats": _build_class_feature_stats(train_test_data),
        "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "algorithm": "RandomForestClassifier",
        "intel_patched": _INTEL_PATCHED,
        "data_source": {
            "data_dir": str(DATA_DIR),
            "manifest": MANIFEST_NAME,
            "steel_type": TARGET_STEEL_TYPE,
            "train_splits_used": ["TRAIN", "TEST"],
            "eval_split_used": "VAL",
        },
        "note": (
            "Load model with joblib.load(model_file). "
            "Input shape: (N, 5) and columns must follow 'features' order exactly."
        ),
    }
    with open(MODEL_INFO_OUT, "w", encoding="utf-8") as f:
        json.dump(model_info, f, indent=2)

    print(f"Saved model artifacts: {MODEL_OUT}, {LABELS_OUT}, {MODEL_INFO_OUT}")


# -- Main ---------------------------------------------------------------------

def main():
    print("Starting weld defect training")

    train_test_data, val_data = load_data_from_manifest(DATA_DIR)

    X_train, y_train, X_val, y_val, le, clean_train_test = preprocess_split_data(
        train_test_data, val_data
    )

    pipeline = train_and_evaluate(X_train, y_train, X_val, y_val, le)
    save_artefacts(pipeline, le, clean_train_test)

    print("Done")


if __name__ == "__main__":
    main()
