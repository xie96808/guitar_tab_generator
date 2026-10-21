import numpy as np

from app.analysis.chords import estimate_chords_per_beat


def test_estimate_chords_basic_major_minor():
    # C major triad energy
    chroma = np.zeros((12, 2), dtype=np.float32)
    chroma[[0, 4, 7], 0] = 1.0
    chroma[[9, 0, 4], 1] = 1.0  # A minor (A C E)
    events = estimate_chords_per_beat(chroma)
    assert events[0].chord == "C"
    assert events[1].chord.endswith("m")
