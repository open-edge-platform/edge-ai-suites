#!/usr/bin/env python3
import argparse
import logging
import pickle
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from sklearnex import config_context, patch_sklearn
except ImportError as exc:
    raise ImportError(
        "scikit-learn-intelex is required. Install with: pip install scikit-learn-intelex"
    ) from exc

patch_sklearn()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run RandomForestRegressor inference and flag generated-power anomalies "
            "with respect to Theoretical_Power_Curve."
        )
    )
    parser.add_argument("--model", type=Path, default=Path("rf_model.pkl"), help="Path to trained PKL model")
    parser.add_argument("--data", type=Path, default=Path("T1.csv"), help="Path to input CSV")
    parser.add_argument(
        "--target",
        type=str,
        default="grid_activepower",
        help="Actual generated power column (optional for scoring if present)",
    )
    parser.add_argument(
        "--theoretical-col",
        type=str,
        default="Theoretical_Power_Curve",
        help="Theoretical power curve column",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("anomaly_predictions.csv"),
        help="Output CSV with predictions and anomaly flags",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "gpu"],
        help="Execution device for sklearnex target offload",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Manual anomaly threshold for |predicted_power - theoretical_power|",
    )
    parser.add_argument(
        "--percentile",
        type=float,
        default=99.0,
        help="If threshold is not set, use this percentile of anomaly score",
    )
    return parser.parse_args()


def get_offload_context(device: str):
    if device == "cpu":
        return nullcontext(), "cpu"

    try:
        import dpctl

        gpu_queue = dpctl.SyclQueue("gpu")
        return config_context(target_offload=gpu_queue), str(gpu_queue)
    except Exception as exc:
        raise RuntimeError(
            "Unable to create GPU SYCL queue. Verify Intel GPU runtime and dpctl installation."
        ) from exc


def get_feature_columns(model, df: pd.DataFrame, target: str) -> list[str]:
    if hasattr(model, "feature_names_in_"):
        cols = [str(c) for c in model.feature_names_in_]
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required feature columns in input CSV: {missing}")
        return cols

    drop = {target, "timestamp"}
    return [c for c in df.columns if c not in drop]


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("sklearnex").setLevel(logging.INFO)

    if not args.model.exists():
        raise FileNotFoundError(f"Model file not found: {args.model}")
    if not args.data.exists():
        raise FileNotFoundError(f"CSV file not found: {args.data}")

    with args.model.open("rb") as f:
        model = pickle.load(f)

    df = pd.read_csv(args.data)

    if args.theoretical_col not in df.columns:
        raise ValueError(f"Theoretical column '{args.theoretical_col}' not found in CSV.")

    feature_cols = get_feature_columns(model, df, args.target)

    X = df[feature_cols].astype(np.float32)
    theoretical_power = df[args.theoretical_col].astype(np.float32).to_numpy(dtype=np.float32)

    offload_ctx, offload_label = get_offload_context(args.device)
    with offload_ctx:
        predicted_power = model.predict(X).astype(np.float32)

    anomaly_score = np.abs(predicted_power - theoretical_power).astype(np.float32)

    threshold = args.threshold
    if threshold is None:
        threshold = float(np.percentile(anomaly_score, args.percentile))

    anomaly_flag = anomaly_score > np.float32(threshold)

    output_df = df.copy()
    output_df["predicted_generated_power"] = predicted_power.astype(np.float32)
    output_df["anomaly_score_vs_theoretical_curve"] = anomaly_score.astype(np.float32)
    output_df["anomaly_flag"] = anomaly_flag

    if args.target in df.columns:
        actual_power = df[args.target].astype(np.float32).to_numpy(dtype=np.float32)
        output_df["actual_minus_theoretical"] = (actual_power - theoretical_power).astype(np.float32)
        output_df["abs_actual_minus_theoretical"] = np.abs(actual_power - theoretical_power).astype(np.float32)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(args.output, index=False)

    print("Inference completed.")
    print(f"Offload device: {offload_label}")
    print(f"Input dtype sample: {X.dtypes.iloc[0]}")
    print(f"Threshold used: {threshold:.6f}")
    print(f"Anomalies detected: {int(anomaly_flag.sum())} / {len(anomaly_flag)}")
    print(f"Saved output: {args.output}")


if __name__ == "__main__":
    main()
