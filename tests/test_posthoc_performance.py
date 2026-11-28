import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from posthoc_performance import calibration_intercept_slope, point_metrics  # noqa: E402


def test_calibration_of_well_calibrated_scores():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.02, 0.98, 20000)
    y = (rng.random(len(p)) < p).astype(int)
    a, b = calibration_intercept_slope(y, p)
    assert abs(a) < 0.05 and abs(b - 1) < 0.05


def test_threshold_metrics():
    y = np.array([1, 1, 0, 0])
    p = np.array([0.9, 0.4, 0.6, 0.1])
    m = point_metrics(y, p)
    assert m["sensitivity"] == 0.5 and m["specificity"] == 0.5
    assert m["accuracy"] == 0.5 and m["balanced_accuracy"] == 0.5 and m["prevalence"] == 0.5
