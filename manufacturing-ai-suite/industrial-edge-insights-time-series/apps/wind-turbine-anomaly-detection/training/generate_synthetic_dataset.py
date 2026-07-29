#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

'''
Summary of generation flow:
 1) Build a full 10-minute timeline for the selected year and randomly keep
    `rows` timestamps to mimic missing SCADA intervals.
 2) Generate wind speed from a Weibull-like distribution and clip to
    realistic operating bounds.
 3) Compute theoretical turbine power using a simple physical power curve
    (cut-in, cubic ramp, rated region, cut-out).
 4) Create measured grid power from theoretical power with efficiency
    variation and Gaussian noise.
 5) Inject operational events (curtailment and high-wind low-power drops)
    to produce anomaly-like behavior.
 6) Clip power to physical limits, round values, and save CSV with columns:
    timestamp, grid_activepower, wind_speed, Theoretical_Power_Curve.
 7) Use `--seed` for reproducibility (same seed -> same synthetic dataset).
'''

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic SCADA dataset with columns compatible with T1.csv."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("synthetic_T1.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50530,
        help="Number of rows to keep after optional gap simulation",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible synthetic data",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2025-01-01 00:00",
        help="Start timestamp for 10-minute series",
    )
    parser.add_argument(
        "--rated-power",
        type=float,
        default=3450.0,
        help="Rated turbine power in kW",
    )
    return parser.parse_args()


def power_curve(wind_speed: np.ndarray, rated_power: float) -> np.ndarray:
    """Simple turbine power curve (cut-in, cubic region, rated, cut-out)."""
    cut_in = 3.0
    rated_speed = 12.0
    cut_out = 25.0

    power = np.zeros_like(wind_speed, dtype=np.float64)

    ramp_mask = (wind_speed >= cut_in) & (wind_speed < rated_speed)
    x = (wind_speed[ramp_mask] - cut_in) / (rated_speed - cut_in)
    power[ramp_mask] = rated_power * (x**3)

    rated_mask = (wind_speed >= rated_speed) & (wind_speed <= cut_out)
    power[rated_mask] = rated_power

    return power

def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    start_ts = pd.to_datetime(args.start)
    end_ts = pd.Timestamp(year=start_ts.year, month=12, day=31, hour=23, minute=50)
    full_index = pd.date_range(start=start_ts, end=end_ts, freq="10min")
    n_full = len(full_index)

    if args.rows > n_full:
        raise ValueError(f"rows must be <= {n_full}, got {args.rows}")

    # Match the original dataset shape by dropping random timestamps.
    keep_idx = np.sort(rng.choice(n_full, size=args.rows, replace=False))
    timestamps = full_index[keep_idx]

    # Wind speed: Weibull-like behavior commonly used for wind modeling.
    wind_speed = rng.weibull(a=2.1, size=args.rows) * 8.4
    wind_speed = np.clip(wind_speed, 0.0, 25.5)

    theoretical = power_curve(wind_speed, rated_power=args.rated_power)

    # Actual power is theoretical power plus losses/noise plus operating events.
    efficiency = 0.88 + rng.normal(loc=0.0, scale=0.08, size=args.rows)
    efficiency = np.clip(efficiency, 0.45, 1.02)

    gaussian_noise = rng.normal(loc=0.0, scale=65.0, size=args.rows)
    grid_activepower = theoretical * efficiency + gaussian_noise

    # Simulate occasional curtailment and low-production events.
    curtail_mask = rng.random(args.rows) < 0.06
    grid_activepower[curtail_mask] *= rng.uniform(0.05, 0.45, size=curtail_mask.sum())

    high_wind_low_power_mask = (wind_speed > 9.0) & (rng.random(args.rows) < 0.02)
    grid_activepower[high_wind_low_power_mask] *= rng.uniform(
        0.02, 0.20, size=high_wind_low_power_mask.sum()
    )

    # Keep physical range similar to source dataset.
    grid_activepower = np.clip(grid_activepower, -5.0, args.rated_power * 1.08)

    df = pd.DataFrame(
        {
            "timestamp": timestamps.strftime("%d %m %Y %H:%M"),
            "grid_activepower": np.round(grid_activepower, 2),
            "wind_speed": np.round(wind_speed, 2),
            "Theoretical_Power_Curve": np.round(theoretical, 2),
        }
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    print(f"Generated synthetic dataset: {args.output}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
