"""Supported confirmatory loss functions."""

from __future__ import annotations

import numpy as np


def squared_loss(observed: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    return (observed - predicted) ** 2


def brier_loss(observed: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    return (observed - np.clip(predicted, 0.0, 1.0)) ** 2
