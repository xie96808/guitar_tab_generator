import json
from pathlib import Path

from app.tab.score import load_fixture_score
from app.tab.transcribe import SCALE_PITCHES, sounding_midis, transcribe_audio

ROOT = Path(__file__).resolve().parents[2] / "scores" / "audio"


def test_synthesized_formats_match_the_known_scale_and_not_the_fixture():
    expected = json.loads((ROOT / "scale.json").read_text())["pitches"]
    assert expected == SCALE_PITCHES
    fixture = load_fixture_score()
    for name in ("scale.wav", "scale.mp3", "scale.m4a"):
        score = transcribe_audio(ROOT / name)
        got = sounding_midis(score)
        hits = sum(abs(found - wanted) <= 1 for found, wanted in zip(got, expected))
        assert hits / len(expected) >= 0.8
        assert len(got) == len(expected)
        beats = [beat for bar in score["tracks"][0]["bars"] for beat in bar["beats"]]
        assert [len(bar["beats"]) for bar in score["tracks"][0]["bars"]] == [4, 4]
        assert all(abs(beat["duration"] * 2 - round(beat["duration"] * 2)) < 1e-6 for beat in beats)
        assert score != fixture
        assert all("string" in note and "fret" in note and "duration" in note for beat in score["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
