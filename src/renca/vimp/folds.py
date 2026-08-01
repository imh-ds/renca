"""Validation helpers for fixed inference folds."""

from __future__ import annotations

import numpy as np

from renca.screening import SplitManifest


def inference_folds(manifest: SplitManifest, row_count: int) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    positions = manifest.inference_row_positions
    if sorted(positions) != sorted(manifest.inference_fold_by_row_position) or any(position >= row_count for position in positions):
        raise ValueError("Split manifest does not assign exactly one valid fold to every inference row")
    folds: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for fold in range(manifest.inference_folds):
        valid = np.array([position for position in positions if manifest.inference_fold_by_row_position[position] == fold])
        if not len(valid):
            raise ValueError(f"Split manifest has no rows in inference fold {fold}")
        train = np.array([position for position in positions if manifest.inference_fold_by_row_position[position] != fold])
        folds[fold] = train, valid
    return folds
