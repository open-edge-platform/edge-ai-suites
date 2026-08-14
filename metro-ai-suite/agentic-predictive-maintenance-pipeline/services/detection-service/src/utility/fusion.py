# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""N-way late fusion of per-modality classification probabilities.

Ported from the ``fuse()`` method of ``SensorFlatHandler`` in
intel/predictive-maintenance-pipeline (src/inference/handlers/sensor_flat.py),
generalized here as a standalone, modality-agnostic utility so any number of
inference branches (image, sensor, or future modalities) can be combined
without depending on a specific handler class.

Each branch contributes a per-class probability vector for a given sample;
branches are combined via a weighted average (weights need not sum to 1 —
the fused vector is renormalized), then the arg-max class is reported as the
final label alongside each contributing branch's confidence for that class,
for auditability.
"""

from typing import Optional


def late_fusion(
    branch_probs: dict[str, dict[str, list[float]]],
    fusion_weights: dict[str, float],
    sample_ids: list[str],
    class_names: dict[int, str],
    metadata_by_sample: Optional[dict[str, dict]] = None,
) -> list[dict]:
    """Fuse per-branch class probabilities into one classification per sample.

    Args:
        branch_probs: Mapping of branch name (e.g. "image", "sensor") to a
            mapping of sample_id -> probability vector (list[float], one
            entry per class, same order as ``class_names``).
        fusion_weights: Mapping of branch name -> weight. Branches missing
            from ``branch_probs`` are skipped. Weights need not sum to 1.
        sample_ids: Sample identifiers to fuse, in output order.
        class_names: Mapping of class index -> class label.
        metadata_by_sample: Optional mapping of sample_id -> extra fields
            (e.g. raw sensor readings) to merge into each result, unchanged.

    Returns:
        List of dicts, one per sample id, each containing: ``source``,
        ``label``, ``confidence``, ``label_id``, ``probabilities`` (dict of
        label -> fused probability), and one ``<branch>_confidence`` field
        per contributing branch (confidence of that branch's own prediction
        for the fused label).
    """
    import numpy as np

    results = []
    n_classes = len(class_names)
    metadata_by_sample = metadata_by_sample or {}
    uniform = [1.0 / n_classes] * n_classes

    for sample_id in sample_ids:
        fused = np.zeros(n_classes)
        branch_arrays = {}

        for branch_name, weight in fusion_weights.items():
            probs_by_sample = branch_probs.get(branch_name)
            if not probs_by_sample:
                continue
            branch_p = np.array(probs_by_sample.get(sample_id, uniform))
            branch_arrays[branch_name] = branch_p
            fused += float(weight) * branch_p

        if fused.sum() == 0:
            fused = np.array(uniform)
        fused = fused / fused.sum()

        best_idx = int(np.argmax(fused))
        result = {
            "source": sample_id,
            "label": class_names.get(best_idx, str(best_idx)),
            "confidence": float(fused[best_idx]),
            "label_id": best_idx,
            "probabilities": {
                class_names.get(i, str(i)): float(fused[i]) for i in range(n_classes)
            },
        }
        for branch_name, branch_p in branch_arrays.items():
            result[f"{branch_name}_confidence"] = float(branch_p[best_idx])
        result.update(metadata_by_sample.get(sample_id, {}))
        results.append(result)

    return results
