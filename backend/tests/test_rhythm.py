import numpy as np

from app.analysis.rhythm import map_onsets_to_hitmask


def test_map_onsets_to_hitmask_marks_hits():
    onsets = np.array([0.0, 0.5, 0.99], dtype=np.float32)
    mask = map_onsets_to_hitmask(onsets, 0.0, 1.0, subdivisions_per_bar=16)
    assert mask.sum() >= 2

