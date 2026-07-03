#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Weld Defect Predictor — Row-by-Row Inference
=============================================
Loads the trained model and provides:

  1. WeldDefectPredictor class  — import and use programmatically
  2. CLI mode                   — pipe / pass individual rows on the command line
  3. Interactive mode           — enter values interactively when run with no args

Intel Acceleration
------------------
Applies Intel Extension for Scikit-learn (scikit-learn-intelex) before loading
the model so that RandomForestClassifier inference runs via the oneDAL backend,
enabling acceleration on Intel CPUs and iGPUs.
Falls back silently to standard scikit-learn if the package is not installed.

Usage (CLI):
    # Single row as space- or comma-separated values
    # Order: Pressure  CO2_Weld_Flow  Feed  Primary_Weld_Current  Secondary_Weld_Voltage
    python weld_defect_predict.py 0.87 18.95 37.58 89.06 24.10

    # Stdin pipe (one row per line)
    echo "0.87,18.95,37.58,89.06,24.10" | python weld_defect_predict.py --stdin

    # Interactive mode
    python weld_defect_predict.py

Programmatic usage:
    from weld_defect_predict import WeldDefectPredictor

    predictor = WeldDefectPredictor()
    result = predictor.predict_row(
        pressure=0.87,
        co2_weld_flow=18.95,
        feed=37.58,
        primary_weld_current=89.06,
        secondary_weld_voltage=24.10,
    )
    print(result)
    # {
    #   "predicted_category": "Excessive Penetration",
    #   "is_defect": true,
    #   "defect_probability": 0.9832,
    #   "probabilities": {
    #       "Burnthrough Weld": 0.0012, ...
    #   }
    # }
"""

import sys
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# ── Intel Extension for Scikit-learn — must be applied BEFORE sklearn/joblib loads ─
try:
    from sklearnex import patch_sklearn
    patch_sklearn(verbose=False)   # accelerates RandomForestClassifier, StandardScaler, etc.
    _INTEL_PATCHED = True
except ImportError:
    _INTEL_PATCHED = False

# ── Constants ──────────────────────────────────────────────────────────────────

MODEL_PATH  = Path(__file__).parent / "weld_defect_model.pkl"
LABELS_PATH = Path(__file__).parent / "weld_defect_labels.pkl"

FEATURES = [
    "Pressure",
    "CO2 Weld Flow",
    "Feed",
    "Primary Weld Current",
    "Secondary Weld Voltage",
]

GOOD_WELD_LABEL = "Good Weld"


# ── Predictor Class ────────────────────────────────────────────────────────────

class WeldDefectPredictor:
    """
    Load once, call predict_row() for every incoming sensor row.

    Parameters
    ----------
    model_path  : path to the trained sklearn pipeline (.pkl)
    labels_path : path to the LabelEncoder (.pkl)
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        labels_path: Path = LABELS_PATH,
    ):
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Run  python weld_defect_train.py  first."
            )
        if not labels_path.exists():
            raise FileNotFoundError(
                f"Label encoder not found at {labels_path}. "
                "Run  python weld_defect_train.py  first."
            )

        self.pipeline = joblib.load(model_path)
        self.le = joblib.load(labels_path)
        self.classes = list(self.le.classes_)

    # ── Core prediction ────────────────────────────────────────────────────────

    def predict_row(
        self,
        pressure: float,
        co2_weld_flow: float,
        feed: float,
        primary_weld_current: float,
        secondary_weld_voltage: float,
    ) -> dict:
        """
        Classify a single sensor reading.

        Returns
        -------
        dict with keys:
            predicted_category : str   — most likely defect class
            is_defect          : bool  — True if class != Good Weld
            defect_probability : float — 1 - P(Good Weld)
            good_weld_probability : float — P(Good Weld)
            confidence         : float — probability of the predicted class
            probabilities      : dict  — per-class probability scores
        """
        row = np.array(
            [[pressure, co2_weld_flow, feed, primary_weld_current, secondary_weld_voltage]],
            dtype=np.float32,
        )

        pred_idx = self.pipeline.predict(row)[0]
        pred_proba = self.pipeline.predict_proba(row)[0]

        predicted_category = self.le.inverse_transform([pred_idx])[0]
        prob_map = {cls: float(round(p, 6)) for cls, p in zip(self.classes, pred_proba)}

        good_weld_prob = prob_map.get(GOOD_WELD_LABEL, 0.0)
        defect_prob = round(1.0 - good_weld_prob, 6)
        confidence = float(round(pred_proba[pred_idx], 6))

        return {
            "predicted_category": predicted_category,
            "is_defect": predicted_category != GOOD_WELD_LABEL,
            "defect_probability": defect_prob,
            "good_weld_probability": round(good_weld_prob, 6),
            "confidence": confidence,
            "probabilities": prob_map,
        }

    def predict_from_dict(self, row: dict) -> dict:
        """
        Accepts a dict with keys matching FEATURES (case-sensitive).
        Convenience wrapper around predict_row().
        """
        return self.predict_row(
            pressure=float(row["Pressure"]),
            co2_weld_flow=float(row["CO2 Weld Flow"]),
            feed=float(row["Feed"]),
            primary_weld_current=float(row["Primary Weld Current"]),
            secondary_weld_voltage=float(row["Secondary Weld Voltage"]),
        )

    def predict_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Batch-predict a DataFrame that contains all FEATURES columns.
        Returns the original DataFrame with prediction columns appended.
        """
        results = [self.predict_from_dict(row) for _, row in df[FEATURES].iterrows()]
        out = df.copy()
        out["predicted_category"]   = [r["predicted_category"]   for r in results]
        out["is_defect"]            = [r["is_defect"]            for r in results]
        out["defect_probability"]   = [r["defect_probability"]   for r in results]
        out["confidence"]           = [r["confidence"]           for r in results]
        return out


# ── CLI helpers ────────────────────────────────────────────────────────────────

def _print_result(result: dict, compact: bool = False):
    if compact:
        flag = "DEFECT" if result["is_defect"] else "OK"
        print(
            f"[{flag}] {result['predicted_category']}"
            f"  confidence={result['confidence']:.4f}"
            f"  defect_prob={result['defect_probability']:.4f}"
        )
    else:
        print(json.dumps(result, indent=2))


def _parse_values(raw: str):
    """Parse a space- or comma-separated string into 5 floats."""
    parts = [v.strip() for v in raw.replace(",", " ").split() if v.strip()]
    if len(parts) != 5:
        raise ValueError(
            f"Expected 5 values (Pressure,CO2_Flow,Feed,Current,Voltage), got {len(parts)}: {raw!r}"
        )
    return [float(p) for p in parts]


def _interactive(predictor: WeldDefectPredictor):
    print("=" * 60)
    print(" WELD DEFECT PREDICTOR — Interactive Mode")
    print(" Enter values when prompted. Type 'quit' to exit.")
    print("=" * 60)
    while True:
        print()
        try:
            vals = {}
            for feat in FEATURES:
                raw = input(f"  {feat}: ").strip()
                if raw.lower() in ("quit", "exit", "q"):
                    print("Exiting.")
                    return
                vals[feat] = float(raw)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return
        except ValueError as e:
            print(f"  ✗ Invalid input: {e}")
            continue

        result = predictor.predict_from_dict(vals)
        print()
        _print_result(result)


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    predictor = WeldDefectPredictor()

    # ── stdin pipe mode: --stdin flag ─────────────────────────────────────────
    if "--stdin" in sys.argv:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                vals = _parse_values(line)
                result = predictor.predict_row(*vals)
                _print_result(result, compact=True)
            except ValueError as e:
                print(f"ERROR: {e}", file=sys.stderr)
        return

    # ── CLI args: values passed directly ─────────────────────────────────────
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        raw = " ".join(args)
        try:
            vals = _parse_values(raw)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print(
                "Usage: python weld_defect_predict.py "
                "<pressure> <co2_flow> <feed> <current> <voltage>"
            )
            sys.exit(1)
        result = predictor.predict_row(*vals)
        _print_result(result)
        return

    # ── Interactive mode ──────────────────────────────────────────────────────
    _interactive(predictor)


if __name__ == "__main__":
    main()
