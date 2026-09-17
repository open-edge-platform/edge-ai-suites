#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Prepare a Qwen VLM weld-defect fine-tuning dataset.

Source (see README.md "Input data" section for the exact schema):
    <input-csv>       — fused vision + time-series predictions with raw sensor readings.
    <images-root>/    — per-class image folders matched by Frame_id stem.

Pipeline:
    1. Parse CSV → strip whitespace, parse output_prediction_details JSON.
    2. Match each row's Frame_id to an image file.
    3. Build a hybrid prompt-response conversation per row:
         - System  : expert weld quality inspector persona.
         - User    : one of 7 rotating prompt variants (sensor data injected).
         - Assistant: classification header + structured analysis block.
    4. Stratified train / validation / test split by weld-session category.
    5. Write all three output formats:
         - HF DatasetDict  (Arrow, castable to PIL image)
         - Per-split parquet files
         - Per-split conversation JSONL (Unsloth vision data-collator compatible)

Usage:
    python prepare_weld_dataset.py \\
        --input-csv path/to/merged_by_ts_time.csv \\
        --images-root path/to/dataset/images \\
        --output-dir path/to/processed_dataset

    Key options:
        --input-csv      Path to the fused sensor+prediction CSV (required)
        --images-root    Root dir of per-class image folders (required)
        --output-dir     Destination for all output artefacts (required)
        --train-ratio / --val-ratio / --test-ratio  (must sum to 1.0)
        --seed           RNG seed for reproducibility
        --limit          Cap rows for dry-runs
        --skip-missing   Drop rows whose image cannot be located
"""

from __future__ import annotations

import argparse
import ast
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple

import pandas as pd
from datasets import Dataset
from datasets import DatasetDict
from datasets import Image as HFImage

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

SENSOR_UNITS: Dict[str, str] = {
    "Primary Weld Current": "A",
    "Secondary Weld Voltage": "V",
    "Pressure": "bar",
    "CO2 Weld Flow": "L/min",
    "Feed": "mm/min",
    "Wire Consumed": "mm",
}

SYSTEM_PROMPT = (
    "You are an expert weld quality inspector and metallurgical engineer with deep knowledge "
    "of MIG/MAG/TIG arc welding processes and industrial weld defect analysis per AWS D1.1 "
    "and ISO 5817 standards. When shown a weld image alongside time-series sensor readings, "
    "you classify the weld quality, identify any defect type, explain the root cause using "
    "sensor evidence, assess severity, and recommend corrective actions. "
    "Always structure your response with clearly labelled sections."
)

# Promptvariations rotation to add diversity in user queries.
USER_PROMPT_TEMPLATES: List[str] = [
    "Analyze this weld image for quality and identify any anomalies.\n{sensor_block}",
    "Based on the provided image and sensor readings, is this weld defective? "
    "If so, classify the defect type.\n{sensor_block}",
    "Inspect this welding process for potential issues such as porosity, undercut, "
    "lack of fusion, or excessive penetration.\n{sensor_block}",
    "Evaluate the structural integrity of this joint using the visual and sensor data "
    "provided. Report your findings.\n{sensor_block}",
    "Check this weld. Provide a full quality assessment and highlight any defects visible "
    "in the image, correlated with the sensor readings.\n{sensor_block}",
    "Review the weld image below and the accompanying process parameters. Classify the weld "
    "quality, describe the defect mechanism (if any), and suggest corrective actions.\n{sensor_block}",
    "Given this weld image and the sensor telemetry, produce a structured weld quality report "
    "covering defect classification, root cause, and remediation steps.\n{sensor_block}",
]


DEFECT_KNOWLEDGE: Dict[str, Dict[str, str]] = {
    "Good_Weld": {
        "visual": (
            "The weld bead exhibits a uniform width, consistent colour, and smooth surface "
            "with no visible anomalies. The arc appears stable with no spatter or irregular "
            "formations. Bead edges show proper fusion with the base metal."
        ),
        "root_cause": "N/A — no defect present.",
        "corrective": "Maintain current process parameters. Continue monitoring sensor telemetry.",
        "severity": "None",
    },
    "Burnthrough": {
        "visual": (
            "A hole or series of holes is visible where the base metal has been completely "
            "melted away. The surrounding area shows heavy discolouration and distortion."
        ),
        "root_cause": (
            "Excessive heat input caused by high current and/or low travel speed exceeded "
            "the material's melting capacity, causing full penetration through the plate."
        ),
        "corrective": (
            "Reduce primary weld current and/or increase travel speed. Verify material "
            "thickness assumptions. Add a backing strip or chill bar if applicable."
        ),
        "severity": "High",
    },
    "Crater_Cracks": {
        "visual": (
            "A star-shaped fracture is visible at the termination point of the weld bead. "
            "The crater at the end of the weld has shrinkage cracks radiating outward."
        ),
        "root_cause": (
            "The weld pool cooled and solidified too rapidly at the end of the pass without "
            "sufficient crater fill, causing shrinkage stress to crack the solidifying metal."
        ),
        "corrective": (
            "Enable and tune crater-fill function (increase crater-fill time and reduce "
            "current slope). Ensure the arc is not abruptly terminated. Review end-of-pass "
            "programming."
        ),
        "severity": "High",
    },
    "Excessive_Convexity": {
        "visual": (
            "The weld bead is excessively convex ('ropey'), standing too high above the base "
            "metal surface relative to its width. Bead toes show incomplete fusion."
        ),
        "root_cause": (
            "Low arc voltage combined with high wire feed speed prevented the filler metal "
            "from wetting out properly into the joint, causing the bead to pile up."
        ),
        "corrective": (
            "Increase secondary weld voltage to improve wetting. Reduce wire feed speed. "
            "Adjust torch angle and travel speed to promote proper bead profile."
        ),
        "severity": "Medium",
    },
    "Excessive_Penetration": {
        "visual": (
            "Excess weld metal is visible protruding significantly through the root side of "
            "the joint. The root bead sags or drips below the base metal surface."
        ),
        "root_cause": (
            "High heat input (elevated current and/or voltage) combined with an oversized "
            "root gap allowed too much molten metal to flow through the joint."
        ),
        "corrective": (
            "Reduce primary weld current and secondary voltage. Tighten root gap per WPS. "
            "Consider a backing bar to support the molten pool."
        ),
        "severity": "Medium",
    },
    "Lack_of_Fusion": {
        "visual": (
            "The bead appears 'cold' with incomplete tie-in at the edges. Unfused zones are "
            "visible between the weld metal and the base metal, often presenting as a groove "
            "or dark line at the bead toe."
        ),
        "root_cause": (
            "Insufficient heat input — low arc voltage resulting in a short arc length — "
            "failed to melt the base metal adequately for proper fusion."
        ),
        "corrective": (
            "Increase secondary weld voltage and primary current to raise heat input. "
            "Slow travel speed. Verify joint fit-up and cleanliness of base metal surfaces."
        ),
        "severity": "High",
    },
    "Overlap": {
        "visual": (
            "Weld metal has flowed over the base metal surface at the toe without fusing to "
            "it. The overlap forms a cold-lap where the bead simply rests on top of the base."
        ),
        "root_cause": (
            "Low current and fast travel speed produced insufficient heat to melt the base "
            "metal, causing filler metal to flow over rather than fuse into the surface."
        ),
        "corrective": (
            "Increase current and reduce travel speed. Check torch angle and electrode "
            "extension. Ensure base metal is clean and free of mill scale or oxide."
        ),
        "severity": "Medium",
    },
    "Porosity": {
        "visual": (
            "Multiple surface pinholes or cavities are visible in or around the weld bead. "
            "In severe cases the bead surface appears pitted."
        ),
        "root_cause": (
            "Gas entrapment in the solidifying weld pool caused by inadequate shielding gas "
            "coverage, contaminated base metal, or moisture in the filler wire."
        ),
        "corrective": (
            "Verify CO2/Ar shielding gas flow rate and check for leaks. Clean base metal "
            "surfaces. Replace any contaminated or wet filler wire. Shield from wind draught."
        ),
        "severity": "Medium",
    },
    "Porosity_w_Excessive_Penetration": {
        "visual": (
            "Multiple surface pinholes are visible alongside excess root protrusion. "
            "The bead surface is pitted and the root bead sags below the base metal plane."
        ),
        "root_cause": (
            "Critically low shielding gas flow failed to protect the weld pool, while an "
            "oversized root gap combined with high heat input allowed contaminated molten "
            "metal to fall through the joint."
        ),
        "corrective": (
            "Restore shielding gas flow to specification. Reduce current and tighten root "
            "gap. Inspect and replace filler wire if contaminated."
        ),
        "severity": "High",
    },
    "Porosity_with_Excessive_Penetration": {
        "visual": (
            "Multiple surface pinholes are visible alongside excess root protrusion. "
            "The bead surface is pitted and the root bead sags below the base metal plane."
        ),
        "root_cause": (
            "Critically low shielding gas flow failed to protect the weld pool, while an "
            "oversized root gap combined with high heat input allowed contaminated molten "
            "metal to fall through the joint."
        ),
        "corrective": (
            "Restore shielding gas flow to specification. Reduce current and tighten root "
            "gap. Inspect and replace filler wire if contaminated."
        ),
        "severity": "High",
    },
    "Spatter": {
        "visual": (
            "Numerous small metal droplets are fused to the base metal adjacent to the weld "
            "bead. The bead surface itself may appear rough or irregular."
        ),
        "root_cause": (
            "An excessively long arc and high current caused an unstable metal transfer "
            "mode, ejecting molten droplets onto the surrounding base metal."
        ),
        "corrective": (
            "Reduce secondary voltage (shorten arc length). Adjust wire feed speed and "
            "inductance settings. Verify correct metal transfer mode for material and "
            "position."
        ),
        "severity": "Low",
    },
    "Undercut": {
        "visual": (
            "A distinct groove or channel is melted into the base metal at the toe of the "
            "weld, running parallel to the bead. The groove reduces the effective cross "
            "section of the base metal."
        ),
        "root_cause": (
            "High current and excessive travel speed caused the arc to 'dig' into the base "
            "metal without leaving enough filler metal to fill the groove."
        ),
        "corrective": (
            "Reduce current and travel speed. Adjust torch angle to direct arc into the "
            "joint rather than the base metal. Add a second pass to fill undercut if present."
        ),
        "severity": "Medium",
    },
    "Warping": {
        "visual": (
            "The base plates have bowed or twisted significantly from their original plane. "
            "Thermal distortion is evident across the weld zone."
        ),
        "root_cause": (
            "High interpass temperature and insufficient mechanical clamping allowed "
            "uncontrolled thermal stresses to pull the plates out of alignment during "
            "heating and cooling."
        ),
        "corrective": (
            "Reduce heat input (lower current/voltage or increase travel speed). Enforce "
            "interpass temperature limits. Use mechanical clamping or pre-set fixtures. "
            "Apply backstep or balanced welding sequence."
        ),
        "severity": "Medium",
    },
}

# Fallback for any unseen category label
_DEFAULT_KNOWLEDGE = {
    "visual": "Visual characteristics are consistent with the classified defect type.",
    "root_cause": "Root cause aligns with sensor deviations from the nominal good-weld profile.",
    "corrective": "Review process parameters and align with qualified WPS specifications.",
    "severity": "Medium",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert merged_by_ts_time.csv + image folders into Unsloth-compatible VLM datasets."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        required=True,
        help="Source CSV file fusing weld classifier predictions with sensor "
        "readings (see README.md 'Input data' section for the required schema).",
    )
    parser.add_argument(
        "--images-root",
        type=Path,
        required=True,
        help="Root directory containing per-class image subfolders, "
        "searched recursively and matched by filename stem (Frame_id).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Destination folder for all output artefacts "
        "(HF DatasetDict, parquet, conversation JSONL, summary.json).",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap on rows processed — useful for quick dry-runs.",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Skip rows whose image cannot be resolved instead of raising an error.",
    )
    return parser.parse_args()


def build_image_index(images_root: Path) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Return {stem -> absolute_path} and {stem -> [all_paths]} for duplicates."""
    index: Dict[str, str] = {}
    duplicates: Dict[str, List[str]] = defaultdict(list)

    for fp in images_root.rglob("*"):
        if not fp.is_file() or fp.suffix.lower() not in SUPPORTED_EXTS:
            continue
        key = fp.stem
        full_path = str(fp.resolve())
        if key in index:
            if not duplicates[key]:
                duplicates[key].append(index[key])
            duplicates[key].append(full_path)
        else:
            index[key] = full_path

    return index, duplicates


def load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, low_memory=False, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    return df


def parse_prediction_details(raw: Any) -> Dict[str, Any]:
    """
    Parse the output_prediction_details JSON string (stored as a Python-dict literal).

    Returns a normalised dict with keys:
        predicted_category, is_defect, defect_probability, good_weld_probability,
        confidence, top_signal_features  (list of dicts)
    """
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        d = ast.literal_eval(raw)
    except Exception:
        return {}

    explanation = d.get("explanation") or {}
    return {
        "predicted_category": d.get("predicted_category", ""),
        "is_defect": bool(d.get("is_defect", False)),
        "defect_probability": float(d.get("defect_probability", 0.0)),
        "good_weld_probability": float(d.get("good_weld_probability", 1.0)),
        "confidence": float(d.get("confidence", 0.0)),
        "top_signal_features": explanation.get("top_signal_features", []),
        "reason": explanation.get("reason", ""),
    }


def build_sensor_block(row: pd.Series) -> str:
    """Format sensor readings into an inline text block."""
    parts = []
    for col, unit in SENSOR_UNITS.items():
        val = row.get(col)
        if pd.notna(val):
            parts.append(f"  • {col}: {val} {unit}")
    return "Sensor Data:\n" + "\n".join(parts) if parts else ""


def build_user_prompt(sensor_block: str, prompt_idx: int) -> str:
    template = USER_PROMPT_TEMPLATES[prompt_idx % len(USER_PROMPT_TEMPLATES)]
    return template.format(sensor_block=sensor_block)


def _lookup(category: str) -> Dict[str, str]:
    """Retrieve defect knowledge, normalising category name variants."""
    clean = category.replace(" ", "_").replace("-", "_")
    # Try exact match first, then case-insensitive scan
    for key in DEFECT_KNOWLEDGE:
        if key.lower() == clean.lower():
            return DEFECT_KNOWLEDGE[key]
    return _DEFAULT_KNOWLEDGE


def build_assistant_response(
    row: pd.Series,
    details: Dict[str, Any],
) -> str:
    """
    Build a hybrid classification + structured analysis response.

    Structure:
        **Weld Classification:** <label>
        **Visual Observation:** <description>
        **Sensor Analysis:** <table of signals vs. expected values>
        **Confidence:** <pct> | **Defect Probability:** <pct>
        **Severity:** <level>
        **Root Cause:** <explanation>
        **Corrective Actions:** <steps>
    """
    predicted_category = details.get("predicted_category", "") or str(
        row.get("vision_classification", "")
    )
    is_defect = details.get("is_defect", False)
    confidence = details.get("confidence", 0.0)
    defect_prob = details.get("defect_probability", 0.0)
    top_features = details.get("top_signal_features", [])

    # Normalise category label for display
    display_label = predicted_category.replace("_", " ").replace("-", " ").title()
    knowledge = _lookup(predicted_category)

    if is_defect:
        classification_line = f"**Weld Classification:** Bad Weld — {display_label}"
    else:
        classification_line = "**Weld Classification:** Good Weld"

    visual_line = f"**Visual Observation:** {knowledge['visual']}"

    # Sensor analysis: merge top_signal_features with raw row readings
    sensor_lines = ["**Sensor Analysis:**"]
    featured_names = {f["feature"] for f in top_features}

    for feat in top_features:
        fname = feat["feature"]
        unit = SENSOR_UNITS.get(fname, "")
        val = feat.get("value", "N/A")
        pred_mean = feat.get("predicted_mean", "N/A")
        gw_mean = feat.get("good_weld_mean", "N/A")
        ev_score = feat.get("evidence_score", 0.0)
        sensor_lines.append(
            f"  • {fname}: {val} {unit} "
            f"(expected for {display_label}: ~{pred_mean:.2f} {unit}; "
            f"good weld mean: ~{gw_mean:.2f} {unit}; "
            f"evidence score: {ev_score:.3f})"
        )

    # Append remaining sensor columns not covered by top_features
    for col, unit in SENSOR_UNITS.items():
        if col not in featured_names:
            val = row.get(col)
            if pd.notna(val):
                sensor_lines.append(f"  • {col}: {val} {unit}")

    # Confidence note — flag low-confidence predictions
    conf_str = f"{confidence:.1%}"
    defect_str = f"{defect_prob:.1%}"
    confidence_line = (
        f"**Model Confidence:** {conf_str} | **Defect Probability:** {defect_str}"
    )
    if confidence < 0.85:
        confidence_line += "  ⚠️ Lower confidence — visual inspection recommended."

    severity_line = f"**Severity:** {knowledge['severity']}"
    root_line = f"**Root Cause:** {knowledge['root_cause']}"
    corrective_line = f"**Corrective Actions:** {knowledge['corrective']}"

    sections = [
        classification_line,
        "",
        visual_line,
        "",
        confidence_line,
        severity_line,
        "",
        root_line,
        "",
        corrective_line,
    ]
    return "\n".join(sections)


def build_conversation(
    image_path: str,
    user_prompt: str,
    assistant_response: str,
) -> List[Dict[str, Any]]:
    """Return a messages list in Unsloth / Qwen-VL chat format."""
    return [
        {
            "role": "system",
            "content": [{"type": "text", "text": SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image", "image": image_path},
            ],
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": assistant_response}],
        },
    ]


def build_records(
    df: pd.DataFrame,
    image_index: Dict[str, str],
    limit: Optional[int],
    skip_missing: bool,
    seed: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Convert each CSV row into one training record with a randomly selected user prompt.

    The prompt variant index is chosen deterministically per row using the RNG seed,
    so dataset generation is fully reproducible.
    """
    records: List[Dict[str, Any]] = []
    missing_frames: List[str] = []
    rng = random.Random(seed)

    rows_iter = df.iterrows()
    processed = 0

    for _, row in rows_iter:
        if limit is not None and processed >= limit:
            break

        frame_id = row.get("Frame_id")
        if not isinstance(frame_id, str) or not frame_id:
            missing_frames.append("<empty_frame_id>")
            if skip_missing:
                continue
            raise ValueError(f"Empty Frame_id encountered at row index {_}.")

        image_path = image_index.get(frame_id)
        if image_path is None:
            missing_frames.append(frame_id)
            if skip_missing:
                continue
            raise FileNotFoundError(
                f"No image found for Frame_id='{frame_id}'. "
                "Check --images-root and image naming convention."
            )

        details = parse_prediction_details(row.get("output_prediction_details"))
        sensor_block = build_sensor_block(row)
        prompt_idx = rng.randint(0, len(USER_PROMPT_TEMPLATES) - 1)
        user_prompt = build_user_prompt(sensor_block, prompt_idx)
        assistant_response = build_assistant_response(row, details)
        messages = build_conversation(image_path, user_prompt, assistant_response)

        # Canonical weld-session label for stratified splitting
        canonical_category = str(
            row.get("Category") or details.get("predicted_category") or "UNKNOWN"
        )

        records.append(
            {
                "id": frame_id,
                "frame_id": frame_id,
                "image": image_path,
                "image_path": image_path,
                "canonical_category": canonical_category,
                "vision_classification": str(row.get("vision_classification") or ""),
                "is_defect": details.get("is_defect", False),
                "defect_probability": details.get("defect_probability", 0.0),
                "confidence": details.get("confidence", 0.0),
                "prompt_variant": prompt_idx,
                "conversation_json": json.dumps(messages, ensure_ascii=False),
                "messages": messages,
            }
        )
        processed += 1

    return records, missing_frames


def stratified_split(
    records: List[Dict[str, Any]],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split records by canonical_category label to preserve class balance."""
    by_label: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_label[record.get("canonical_category") or "UNKNOWN"].append(record)

    rng = random.Random(seed)
    split_records: Dict[str, List[Dict[str, Any]]] = {
        "train": [],
        "validation": [],
        "test": [],
    }

    for label_records in by_label.values():
        rng.shuffle(label_records)
        n = len(label_records)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        n_test = n - n_train - n_val

        # Guarantee at least one sample per split when enough data exists.
        if n >= 3:
            if n_train == 0:
                n_train = 1
            if n_val == 0:
                n_val = 1
            if n_test == 0:
                n_test = 1
            while n_train + n_val + n_test > n:
                if n_train >= n_val and n_train >= n_test and n_train > 1:
                    n_train -= 1
                elif n_val >= n_test and n_val > 1:
                    n_val -= 1
                elif n_test > 1:
                    n_test -= 1
                else:
                    break

        split_records["train"].extend(label_records[:n_train])
        split_records["validation"].extend(label_records[n_train : n_train + n_val])
        split_records["test"].extend(label_records[n_train + n_val :])

    for split_name in split_records:
        rng.shuffle(split_records[split_name])

    return split_records


# ── Output helpers ─────────────────────────────────────────────────────────────


def write_jsonl(records: Iterable[Dict[str, Any]], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        for row in records:
            # Write only the conversation structure (messages list) per line —
            # this is what Unsloth's vision data collator expects.
            f.write(
                json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n"
            )


def build_hf_dataset(split_rows: List[Dict[str, Any]]) -> Dataset:
    """Build a HF Dataset with scalar columns; cast image column to PIL-loadable Image."""
    hf_rows = [
        {
            "id": row["id"],
            "frame_id": row["frame_id"],
            "image": row["image"],
            "image_path": row["image_path"],
            "canonical_category": row.get("canonical_category"),
            "vision_classification": row.get("vision_classification", ""),
            "is_defect": row.get("is_defect", False),
            "defect_probability": row.get("defect_probability", 0.0),
            "confidence": row.get("confidence", 0.0),
            "prompt_variant": row.get("prompt_variant", 0),
            "conversation_json": row.get("conversation_json", "[]"),
        }
        for row in split_rows
    ]
    ds = Dataset.from_list(hf_rows)
    return ds.cast_column("image", HFImage())


def ensure_ratios(train: float, val: float, test: float) -> None:
    total = train + val + test
    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            f"Split ratios must sum to 1.0. Got {train} + {val} + {test} = {total:.6f}."
        )


def main() -> None:
    args = parse_args()
    ensure_ratios(args.train_ratio, args.val_ratio, args.test_ratio)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] Building image index from: {args.images_root}")
    image_index, duplicates = build_image_index(args.images_root)
    if duplicates:
        print(
            f"[warn] {len(duplicates)} duplicate image stems found; first path used for each."
        )

    print(f"[info] Loading CSV: {args.input_csv}")
    df = load_csv(args.input_csv)
    print(f"[info] CSV loaded: {len(df)} rows, {len(df.columns)} columns.")

    print("[info] Building training records ...")
    records, missing_frames = build_records(
        df=df,
        image_index=image_index,
        limit=args.limit,
        skip_missing=args.skip_missing,
        seed=args.seed,
    )

    if not records:
        raise RuntimeError(
            "No records were built. Verify --input-csv and --images-root."
        )

    print(
        f"[info] Records built: {len(records)} | Missing images: {len(missing_frames)}"
    )

    print("[info] Performing stratified split ...")
    split_rows = stratified_split(
        records,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    # Build HF datasets
    split_datasets = {name: build_hf_dataset(rows) for name, rows in split_rows.items()}
    dataset_dict = DatasetDict(split_datasets)

    # ── Write HF DatasetDict ──
    hf_dir = args.output_dir / "hf_dataset"
    print(f"[info] Saving HF DatasetDict to: {hf_dir}")
    dataset_dict.save_to_disk(str(hf_dir))

    # ── Write per-split parquet + JSONL ──
    parquet_dir = args.output_dir / "parquet"
    conv_dir = args.output_dir / "conversations"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    conv_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "input_csv": str(args.input_csv.resolve()),
        "images_root": str(args.images_root.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "total_records": len(records),
        "missing_frames_count": len(missing_frames),
        "prompt_variants": len(USER_PROMPT_TEMPLATES),
        "splits": {},
    }

    for split_name, ds in dataset_dict.items():
        parquet_path = parquet_dir / f"{split_name}.parquet"
        ds.to_parquet(str(parquet_path))

        conv_path = conv_dir / f"{split_name}.jsonl"
        write_jsonl(split_rows[split_name], conv_path)

        summary["splits"][split_name] = {
            "count": len(ds),
            "parquet_path": str(parquet_path.resolve()),
            "conversation_jsonl_path": str(conv_path.resolve()),
        }
        print(
            f"  [{split_name}] {len(ds)} samples → {parquet_path.name}, {conv_path.name}"
        )

    summary["missing_frames_sample"] = missing_frames[:20]
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n Weld VLM dataset prepared successfully.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
