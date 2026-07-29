#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Training script for RandomForestRegressor using Intel scikit-learn extension for wind turbine anomaly detection. """

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

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a RandomForestRegressor with Intel scikit-learn extension for wind turbine anomaly detection."
    )
    parser.add_argument("--data", type=Path, default=Path("T1.csv"), help="Path to input CSV file")
    parser.add_argument(
        "--target",
        type=str,
        default="grid_activepower",
        help="Name of the regression target column",
    )
    parser.add_argument(
        "--features",
        type=str,
        nargs="*",
        default=["wind_speed"],
        help="Feature columns to use (default: wind_speed only)",
    )
    parser.add_argument(
        "--output-model",
        type=Path,
        default=Path("rf_anomaly_model.pkl"),
        help="Output path for serialized model (.pkl)",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split ratio")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument("--n-estimators", type=int, default=300, help="Number of trees")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum tree depth")
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "gpu"],
        help="Execution device for sklearnex target offload",
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


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("sklearnex").setLevel(logging.INFO)

    if not args.data.exists():
        raise FileNotFoundError(f"CSV file not found: {args.data}")

    df = pd.read_csv(args.data)

    if args.target not in df.columns:
        raise ValueError(f"Target column '{args.target}' not found in CSV.")

    missing_features = [f for f in args.features if f not in df.columns]
    if missing_features:
        raise ValueError(f"Missing feature columns in CSV: {missing_features}")

    # Ensure all model inputs are explicitly float32 while preserving feature names and order.
    X = df[args.features].astype(np.float32)
    y = df[args.target].astype(np.float32)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    model = RandomForestRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        random_state=args.random_state,
        n_jobs=-1,
    )

    offload_ctx, offload_label = get_offload_context(args.device)
    with offload_ctx:
        model.fit(X_train, y_train)
        predictions = model.predict(X_test).astype(np.float32)

    y_test_np = y_test.to_numpy(dtype=np.float32)
    rmse = np.sqrt(mean_squared_error(y_test_np, predictions))
    mae = mean_absolute_error(y_test_np, predictions)
    r2 = r2_score(y_test_np, predictions)

    print("Training completed.")
    print(f"Features: {args.features}")
    print(f"Offload device: {offload_label}")
    print(f"X dtype: {X.dtypes.iloc[0]}, y dtype: {y.dtype}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE : {mae:.4f}")
    print(f"R2  : {r2:.4f}")

    args.output_model.parent.mkdir(parents=True, exist_ok=True)
    with args.output_model.open("wb") as f:
        pickle.dump(model, f)

    print(f"Saved model: {args.output_model}")


if __name__ == "__main__":
    main()
