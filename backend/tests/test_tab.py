from app.tab.fingering import FretNote, finger_beats
from app.tab.gp5 import beats_from_gp5_bytes, fixture_note_rows, score_to_gp5_bytes
from app.tab.score import load_fixture_score


def _frets_low_to_high(beat: list[FretNote]) -> list[int]:
    return [note.fret for note in sorted(beat, key=lambda note: -note.string)]


def _pitches(beat: list[FretNote]) -> list[int]:
    return sorted(note.midi for note in beat)


def _span(beat: list[FretNote]) -> int:
    frets = [note.fret for note in beat]
    return max(frets) - min(frets)


def _position_changes(beats: list[list[FretNote]]) -> int:
    changes = 0
    for left, right in zip(beats, beats[1:]):
        left_pressed = [note.fret for note in left if note.fret >= 1]
        right_pressed = [note.fret for note in right if note.fret >= 1]
        if left_pressed and right_pressed and abs(min(left_pressed) - min(right_pressed)) > 4:
            changes += 1
    return changes


def test_c_major_scale_stays_in_first_position():
    pitches = [48, 50, 52, 53, 55, 57, 59, 60]
    beats = finger_beats([[pitch] for pitch in pitches])
    assert [_pitches(beat) for beat in beats] == [[pitch] for pitch in pitches]
    assert all(0 <= note.fret <= 4 for beat in beats for note in beat)


def test_open_chords_use_open_shapes():
    shapes = {
        "Em": ([40, 47, 52, 55, 59, 64], [0, 2, 2, 0, 0, 0], 6),
        "G": ([43, 47, 50, 55, 59, 67], [3, 2, 0, 0, 0, 3], 6),
        "C": ([48, 52, 55, 60, 64], [3, 2, 0, 1, 0], 5),
        "D": ([50, 57, 62, 66], [0, 2, 3, 2], 4),
    }
    for name, (pitches, frets, string_count) in shapes.items():
        beat = finger_beats([pitches])[0]
        assert _pitches(beat) == sorted(pitches), name
        assert _frets_low_to_high(beat) == frets, name
        assert _span(beat) <= 4, name
        assert len(beat) == string_count, name
        if name == "C":
            assert all(note.string != 6 for note in beat)
        if name == "D":
            assert {note.string for note in beat} == {1, 2, 3, 4}


def test_wider_solo_changes_position_twice():
    beats = finger_beats([[41], [69, 72], [41]])
    assert [_pitches(beat) for beat in beats] == [[41], [69, 72], [41]]
    assert _span(beats[1]) <= 4
    assert all(_span(beat) <= 4 for beat in beats)
    assert _position_changes(beats) == 2


def test_fixture_gp5_round_trip_keeps_string_fret_and_duration():
    score = load_fixture_score()
    expected = fixture_note_rows(score)
    flat = [note for beat in expected for note in beat["notes"]]
    assert any(note["duration"] == 1 for note in flat)
    assert any(note["duration"] == 0.5 for note in flat)
    assert any(len(beat["notes"]) >= 2 for beat in expected)
    assert any(note["fret"] == 0 for note in flat)

    data = score_to_gp5_bytes(score)
    parsed = beats_from_gp5_bytes(data)
    assert parsed == expected
    assert parsed[1]["duration"] * 2 == parsed[0]["duration"]
