#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Inference example script for RandomForestRegressor using Intel scikit-learn extension for wind turbine anomaly detection. """

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

logging.getLogger("sklearnex").setLevel(logging.INFO)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RandomForestRegressor inference and flag anomalies based on residuals and threshold."
    )
    parser.add_argument("--model", type=Path, default=Path("rf_anomaly_model.pkl"), help="Path to trained PKL model")
    parser.add_argument("--data", type=Path, default=Path("../simulation-data/wind-turbine-anomaly-detection.csv"), help="Path to input CSV for inference")
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
    # Physics-based operating range filters (same as original notebook)
    parser.add_argument("--cut-in-speed", type=float, default=3.0, help="Min wind speed (m/s) for power generation")
    parser.add_argument("--cut-out-speed", type=float, default=14.0, help="Max wind speed (m/s) for power generation")
    parser.add_argument("--min-power", type=float, default=50.0, help="Min expected power (kW) within operating range")
    # Error threshold: fraction of predicted power — row is anomalous if actual deviates by more than this
    parser.add_argument("--error-threshold", type=float, default=0.15, help="Relative error threshold to flag anomaly (default: 0.15 = 15%)")
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

    # Get expected feature columns from model
    if hasattr(model, "feature_names_in_"):
        feature_cols = list(model.feature_names_in_)
    else:
        feature_cols = [c for c in df.columns if c != "grid_active_power"]
    
    missing_features = [c for c in feature_cols if c not in df.columns]
    if missing_features:
        raise ValueError(f"Missing required feature columns in input CSV: {missing_features}")

    X = df[feature_cols].astype(np.float32)
    has_actual = "grid_active_power" in df.columns

    # Process each row individually
    predicted_power_list = []
    anomaly_status_list = []
    error_list = []

    offload_ctx, offload_label = get_offload_context(args.device)

    with offload_ctx:
        for idx, row in X.iterrows():
            wind_speed = float(df.loc[idx, "wind_speed"])
            row_array = row.values.reshape(1, -1).astype(np.float32)
            pred = np.float32(model.predict(row_array)[0])
            predicted_power_list.append(pred)

            status = None
            rel_error = np.float32(0.0)

            if has_actual:
                actual = np.float32(df.loc[idx, "grid_active_power"])

                # Physics-based filter: skip rows outside turbine operating range
                # Mirrors original notebook logic without LinearRegression
                outside_range = (
                    wind_speed <= args.cut_in_speed
                    or wind_speed > args.cut_out_speed
                    or (wind_speed > args.cut_in_speed and actual < np.float32(args.min_power))
                )

                if not outside_range and pred > np.float32(0.0):
                    # Relative error vs predicted (avoids division by near-zero actual)
                    rel_error = np.float32((pred - actual) / pred)
                    if rel_error > np.float32(args.error_threshold):
                        if rel_error < np.float32(0.30):
                            status = "LOW"
                        elif rel_error < np.float32(0.60):
                            status = "MEDIUM"
                        else:
                            status = "HIGH"

            anomaly_status_list.append(status)
            error_list.append(rel_error)

    # Build output dataframe
    output_df = df.copy()
    output_df["predicted_power"] = np.array(predicted_power_list, dtype=np.float32)
    output_df["relative_error"] = np.array(error_list, dtype=np.float32)
    output_df["anomaly_status"] = anomaly_status_list

    if has_actual:
        count_low = anomaly_status_list.count("LOW")
        count_med = anomaly_status_list.count("MEDIUM")
        count_high = anomaly_status_list.count("HIGH")
        count_normal = len(anomaly_status_list) - count_low - count_med - count_high

        print("Inference completed (row-by-row).")
        print(f"Offload device: {offload_label}")
        print(f"Input dtype sample: {X.dtypes.iloc[0]}")
        print(f"Error threshold: {args.error_threshold} ({args.error_threshold*100:.0f}%)")
        print(f"Operating range: wind {args.cut_in_speed}–{args.cut_out_speed} m/s, min power {args.min_power} kW")
        print(f"Anomaly status breakdown: NORMAL={count_normal}, LOW={count_low}, MEDIUM={count_med}, HIGH={count_high}")
    else:
        print("Inference completed (row-by-row).")
        print(f"Offload device: {offload_label}")
        print(f"Input dtype sample: {X.dtypes.iloc[0]}")
        print("Note: No 'grid_active_power' column found; anomaly detection not computed.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(args.output, index=False)
    print(f"Saved output: {args.output}")


if __name__ == "__main__":
    main()
