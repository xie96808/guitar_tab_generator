from app.tab.drafts import (
    empty_score,
    midi_file,
    parse_ascii,
    parse_chords,
    parse_jianpu,
    parse_midi,
    parse_musicxml,
    read_draft_file,
)
from app.tab.edits import apply_edit
from app.tab.gp5 import score_from_gp5_bytes, score_to_gp5_bytes
from app.tab.score import load_fixture_score


def _rows(score):
    rows = []
    for bar in score["tracks"][0]["bars"]:
        for beat in bar["beats"]:
            if beat.get("rest"):
                continue
            rows.append([(note["string"], note["fret"], note["duration"]) for note in beat["notes"]])
    return rows


def _round_trip(score):
    parsed = score_from_gp5_bytes(score_to_gp5_bytes(score))
    return parsed


def test_jianpu_chord_ascii_midi_and_musicxml_match_expected_frets():
    jianpu = parse_jianpu("key C\ntime 4/4\n1 2 3 5 | 6 5 3 2\n")
    assert _rows(jianpu)[0][0][2] == 1
    assert [note[1] for beat in _rows(jianpu) for note in beat]
    pitches = []
    from app.tab.fingering import OPEN_MIDI

    for beat in _rows(jianpu):
        string, fret, _duration = beat[0]
        pitches.append(OPEN_MIDI[string] + fret)
    assert pitches == [60, 62, 64, 67, 69, 67, 64, 62]
    assert len(jianpu["tracks"][0]["bars"]) == 2
    assert [len(bar["beats"]) for bar in jianpu["tracks"][0]["bars"]] == [4, 4]

    chords = parse_chords("Em G | C D\n")
    frets = []
    assert len(chords["tracks"][0]["bars"]) == 2
    for bar in chords["tracks"][0]["bars"]:
        for beat in bar["beats"]:
            ordered = sorted(beat["notes"], key=lambda note: -note["string"])
            frets.append([note["fret"] for note in ordered])
    assert frets == [[0, 2, 2, 0, 0, 0], [3, 2, 0, 0, 0, 3], [3, 2, 0, 1, 0], [0, 2, 3, 2]]

    ascii_score = parse_ascii("e|--0--3--|\nB|--1-----|\nG|--------|\nD|--------|\nA|--------|\nE|--------|\n")
    assert _rows(ascii_score)[0] == [(1, 0, 1.0), (2, 1, 1.0)]
    assert _rows(ascii_score)[1] == [(1, 3, 1.0)]

    midi = parse_midi(midi_file([(60, 0, 480), (64, 480, 480)]))
    midi_pitches = [OPEN_MIDI[row[0][0]] + row[0][1] for row in _rows(midi)]
    assert midi_pitches == [60, 64]

    xml = """<?xml version="1.0"?>
    <score-partwise>
      <part>
        <measure>
          <attributes><divisions>1</divisions></attributes>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
          <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration></note>
        </measure>
      </part>
    </score-partwise>"""
    music = parse_musicxml(xml)
    music_pitches = [OPEN_MIDI[row[0][0]] + row[0][1] for row in _rows(music)]
    assert music_pitches == [60, 64]
    assert read_draft_file("song.mid", midi_file([(60, 0, 480)]) )["title"] == "MIDI"


def test_exports_gp_header_and_is_not_the_handwritten_fixture():
    score = parse_jianpu("key C\ntime 4/4\n1 2 3\n")
    data = score_to_gp5_bytes(score)
    assert data[1:4] == b"FIC"
    parsed = score_from_gp5_bytes(data)
    assert _rows(parsed) == _rows(score)
    assert parsed != load_fixture_score()


def test_every_listed_edit_round_trips_through_gp5():
    score = parse_jianpu("key C\ntime 4/4\n1 2 3 5\n")
    score = apply_edit(score, {"op": "set_fret", "bar": 0, "beat": 0, "note": 0, "fret": 5})
    score = apply_edit(score, {"op": "set_string", "bar": 0, "beat": 0, "note": 0, "string": 3})
    score = apply_edit(score, {"op": "set_duration", "bar": 0, "beat": 1, "duration": 1, "dotted": True})
    score = apply_edit(score, {"op": "set_tempo", "tempo": 96})
    score = apply_edit(score, {"op": "set_time_signature", "numerator": 3, "denominator": 4})
    score = apply_edit(score, {"op": "set_key", "key": "G"})
    score = apply_edit(score, {"op": "set_dynamic", "bar": 0, "beat": 0, "note": 0, "dynamic": "p"})
    score = apply_edit(score, {"op": "set_dynamic", "bar": 0, "beat": 2, "note": 0, "dynamic": "mf"})
    score = apply_edit(score, {"op": "set_hammer", "bar": 0, "beat": 0, "note": 0})
    score = apply_edit(score, {"op": "set_pull", "bar": 0, "beat": 1, "note": 0})
    score = apply_edit(score, {"op": "set_slide", "bar": 0, "beat": 2, "note": 0})
    score = apply_edit(score, {"op": "set_bend", "bar": 0, "beat": 1, "note": 0, "semitones": 1})
    score = apply_edit(score, {"op": "set_vibrato", "bar": 0, "beat": 1, "note": 0})
    score = apply_edit(score, {"op": "set_palm_mute", "bar": 0, "beat": 2, "note": 0})
    score = apply_edit(score, {"op": "set_dead", "bar": 0, "beat": 2, "note": 0})
    score = apply_edit(score, {"op": "set_tie", "bar": 0, "beat": 1, "note": 0})
    score = apply_edit(score, {"op": "set_chord", "bar": 0, "beat": 0, "name": "Em"})
    score = apply_edit(score, {"op": "add_note", "bar": 0, "beat": 0, "string": 1, "fret": 0})
    score = apply_edit(score, {"op": "set_rest", "bar": 0, "beat": 3})
    score = apply_edit(score, {"op": "set_repeat", "start": 0, "end": 0, "count": 2})
    score = apply_edit(score, {"op": "copy_bar", "bar": 0})
    before_delete = len(score["tracks"][0]["bars"])
    score = apply_edit(score, {"op": "delete_bar", "bar": 1})
    assert len(score["tracks"][0]["bars"]) == before_delete - 1
    score = apply_edit(score, {"op": "quantize", "grid": 0.5})
    parsed = _round_trip(score)
    beat = parsed["tracks"][0]["bars"][0]["beats"][0]
    assert beat["notes"][0]["fret"] == 5 or any(note["fret"] == 5 for note in beat["notes"])
    assert parsed["tempo"] == 96
    assert parsed["timeSignature"] == "3/4"
    assert parsed["keySignature"] == "G"
    assert any(note["dynamic"] == "p" for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["dynamic"] == "mf" for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["hammer"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["slide"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["bend"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["vibrato"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["palmMute"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["dead"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(note["tie"] for beat in parsed["tracks"][0]["bars"][0]["beats"] for note in beat["notes"])
    assert any(beat["chord"] == "Em" for beat in parsed["tracks"][0]["bars"][0]["beats"])
    assert any(beat["rest"] for beat in parsed["tracks"][0]["bars"][0]["beats"])
    assert parsed["tracks"][0]["bars"][0]["repeatStart"] is True
    assert parsed["tracks"][0]["bars"][0]["repeatEnd"] == 2
    assert any(abs(beat["duration"] - 1.5) < 1e-6 for beat in parsed["tracks"][0]["bars"][0]["beats"])


def test_fret_delete_meter_and_dynamic_change_gp5_bytes():
    base = parse_jianpu("key C\ntime 4/4\n1 2 3\n")
    original = score_to_gp5_bytes(base)
    changed = apply_edit(base, {"op": "set_fret", "bar": 0, "beat": 0, "note": 0, "fret": 7})
    assert score_from_gp5_bytes(score_to_gp5_bytes(changed))["tracks"][0]["bars"][0]["beats"][0]["notes"][0]["fret"] == 7
    deleted = apply_edit(base, {"op": "delete_note", "bar": 0, "beat": 0, "note": 0})
    assert score_from_gp5_bytes(score_to_gp5_bytes(deleted))["tracks"][0]["bars"][0]["beats"][0]["rest"] is True
    meter = apply_edit(base, {"op": "set_time_signature", "numerator": 6, "denominator": 8})
    assert score_from_gp5_bytes(score_to_gp5_bytes(meter))["timeSignature"] == "6/8"
    loud = apply_edit(base, {"op": "set_dynamic", "bar": 0, "beat": 0, "note": 0, "dynamic": "p"})
    assert score_to_gp5_bytes(loud) != original
    blank = apply_edit(empty_score(), {"op": "add_note", "bar": 0, "beat": 0, "string": 1, "fret": 3})
    assert score_from_gp5_bytes(score_to_gp5_bytes(blank))["tracks"][0]["bars"][0]["beats"][0]["notes"][0]["fret"] == 3


def test_descending_hammer_stays_hammer_in_gp5():
    score = apply_edit(
        parse_ascii("e|--5--3--|\nB|--------|\nG|--------|\nD|--------|\nA|--------|\nE|--------|\n"),
        {"op": "set_hammer", "bar": 0, "beat": 0, "note": 0},
    )
    parsed = score_from_gp5_bytes(score_to_gp5_bytes(score))
    note = parsed["tracks"][0]["bars"][0]["beats"][0]["notes"][0]
    following = parsed["tracks"][0]["bars"][0]["beats"][1]["notes"][0]
    assert note["fret"] > following["fret"]
    assert note["hammer"] is True
    assert note["pull"] is False


def test_pull_on_ascending_jianpu_survives_gp5():
    score = apply_edit(parse_jianpu("key C\ntime 4/4\n1 2\n"), {"op": "set_pull", "bar": 0, "beat": 0, "note": 0})
    parsed = score_from_gp5_bytes(score_to_gp5_bytes(score))
    note = parsed["tracks"][0]["bars"][0]["beats"][0]["notes"][0]
    following = parsed["tracks"][0]["bars"][0]["beats"][1]["notes"][0]
    assert note["fret"] < following["fret"]
    assert note["pull"] is True
    assert note["hammer"] is False


def test_barlines_give_one_chord_per_bar():
    chords = parse_chords("Em | G | C | D\n")
    assert len(chords["tracks"][0]["bars"]) == 4
    assert [bar["beats"][0]["chord"] for bar in chords["tracks"][0]["bars"]] == ["Em", "G", "C", "D"]


def test_gp5_readback_matches_fret_string_dot_pull_and_transpose():
    from app.tab.fingering import OPEN_MIDI

    base = parse_jianpu("key C\ntime 4/4\n1 2 3\n")
    fretted = apply_edit(base, {"op": "set_fret", "bar": 0, "beat": 0, "note": 0, "fret": 7})
    fretted = apply_edit(fretted, {"op": "set_string", "bar": 0, "beat": 0, "note": 0, "string": 4})
    fretted = apply_edit(fretted, {"op": "set_duration", "bar": 0, "beat": 1, "duration": 1, "dotted": True})
    parsed = score_from_gp5_bytes(score_to_gp5_bytes(fretted))
    first = parsed["tracks"][0]["bars"][0]["beats"][0]["notes"][0]
    second = parsed["tracks"][0]["bars"][0]["beats"][1]
    assert first["fret"] == 7
    assert first["string"] == 4
    assert abs(second["duration"] - 1.5) < 1e-6
    assert abs(second["notes"][0]["duration"] - 1.5) < 1e-6

    pulled = apply_edit(
        parse_ascii("e|--5--3--|\nB|--------|\nG|--------|\nD|--------|\nA|--------|\nE|--------|\n"),
        {"op": "set_pull", "bar": 0, "beat": 0, "note": 0},
    )
    pull_back = score_from_gp5_bytes(score_to_gp5_bytes(pulled))
    assert pull_back["tracks"][0]["bars"][0]["beats"][0]["notes"][0]["pull"] is True

    moved = apply_edit(parse_jianpu("key C\ntime 4/4\n1\n"), {"op": "transpose", "semitones": 2})
    moved_back = score_from_gp5_bytes(score_to_gp5_bytes(moved))
    note = moved_back["tracks"][0]["bars"][0]["beats"][0]["notes"][0]
    assert OPEN_MIDI[note["string"]] + note["fret"] == 62


def _gp5(score):
    return score_from_gp5_bytes(score_to_gp5_bytes(score))


def _note(score, bar, beat, index=0):
    return score["tracks"][0]["bars"][bar]["beats"][beat]["notes"][index]


def test_each_edit_changes_memory_and_gp5_readback():
    from app.tab.fingering import OPEN_MIDI

    base = parse_jianpu("key C\ntime 4/4\n1 2 3 5\n")

    def both(edited, check):
        assert check(edited)
        assert check(_gp5(edited))

    fretted = apply_edit(base, {"op": "set_fret", "bar": 0, "beat": 0, "note": 0, "fret": 8})
    both(fretted, lambda score: _note(score, 0, 0)["fret"] == 8 and _note(score, 0, 0)["fret"] != _note(base, 0, 0)["fret"])

    restrung = apply_edit(base, {"op": "set_string", "bar": 0, "beat": 0, "note": 0, "string": 4})
    both(restrung, lambda score: _note(score, 0, 0)["string"] == 4)

    dotted = apply_edit(base, {"op": "set_duration", "bar": 0, "beat": 0, "duration": 1, "dotted": True})
    both(dotted, lambda score: abs(score["tracks"][0]["bars"][0]["beats"][0]["duration"] - 1.5) < 1e-6)

    tempo = apply_edit(base, {"op": "set_tempo", "tempo": 88})
    both(tempo, lambda score: score["tempo"] == 88 and score["tempo"] != base["tempo"])

    meter = apply_edit(base, {"op": "set_time_signature", "numerator": 6, "denominator": 8})
    both(meter, lambda score: score["timeSignature"] == "6/8")

    keyed = apply_edit(base, {"op": "set_key", "key": "G"})
    both(keyed, lambda score: score["keySignature"] == "G")

    for level in ("p", "mf"):
        dynamic = apply_edit(base, {"op": "set_dynamic", "bar": 0, "beat": 1, "note": 0, "dynamic": level})
        both(dynamic, lambda score, level=level: _note(score, 0, 1)["dynamic"] == level and _note(base, 0, 1)["dynamic"] != level)
    forte = apply_edit(
        apply_edit(base, {"op": "set_dynamic", "bar": 0, "beat": 1, "note": 0, "dynamic": "p"}),
        {"op": "set_dynamic", "bar": 0, "beat": 1, "note": 0, "dynamic": "f"},
    )
    both(forte, lambda score: _note(score, 0, 1)["dynamic"] == "f")

    rested = apply_edit(base, {"op": "set_rest", "bar": 0, "beat": 0})
    both(rested, lambda score: score["tracks"][0]["bars"][0]["beats"][0]["rest"] is True and score["tracks"][0]["bars"][0]["beats"][0]["notes"] == [])

    tied = apply_edit(base, {"op": "set_tie", "bar": 0, "beat": 1, "note": 0})
    both(tied, lambda score: _note(score, 0, 1)["tie"] is True)

    named = apply_edit(base, {"op": "set_chord", "bar": 0, "beat": 0, "name": "Em"})
    both(named, lambda score: score["tracks"][0]["bars"][0]["beats"][0]["chord"] == "Em")

    repeated = apply_edit(base, {"op": "set_repeat", "start": 0, "end": 0, "count": 2})
    both(repeated, lambda score: score["tracks"][0]["bars"][0]["repeatStart"] is True and score["tracks"][0]["bars"][0]["repeatEnd"] == 2)

    hammered = apply_edit(base, {"op": "set_hammer", "bar": 0, "beat": 0, "note": 0})
    both(hammered, lambda score: _note(score, 0, 0)["hammer"] is True and _note(score, 0, 0)["pull"] is False)

    pulled = apply_edit(base, {"op": "set_pull", "bar": 0, "beat": 0, "note": 0})
    both(pulled, lambda score: _note(score, 0, 0)["pull"] is True and _note(score, 0, 0)["hammer"] is False)

    slid = apply_edit(base, {"op": "set_slide", "bar": 0, "beat": 0, "note": 0})
    both(slid, lambda score: _note(score, 0, 0)["slide"] is True)

    bent = apply_edit(base, {"op": "set_bend", "bar": 0, "beat": 0, "note": 0, "semitones": 1})
    both(bent, lambda score: _note(score, 0, 0)["bend"] is True)

    vibrato = apply_edit(base, {"op": "set_vibrato", "bar": 0, "beat": 0, "note": 0})
    both(vibrato, lambda score: _note(score, 0, 0)["vibrato"] is True)

    muted = apply_edit(base, {"op": "set_palm_mute", "bar": 0, "beat": 0, "note": 0})
    both(muted, lambda score: _note(score, 0, 0)["palmMute"] is True)

    dead = apply_edit(base, {"op": "set_dead", "bar": 0, "beat": 0, "note": 0})
    both(dead, lambda score: _note(score, 0, 0)["dead"] is True)

    added = apply_edit(empty_score(), {"op": "add_note", "bar": 0, "beat": 0, "string": 2, "fret": 4})
    both(added, lambda score: score["tracks"][0]["bars"][0]["beats"][0]["notes"][0]["fret"] == 4)

    deleted = apply_edit(base, {"op": "delete_note", "bar": 0, "beat": 0, "note": 0})
    both(deleted, lambda score: score["tracks"][0]["bars"][0]["beats"][0]["rest"] is True)

    copied = apply_edit(base, {"op": "copy_bar", "bar": 0})
    both(copied, lambda score: len(score["tracks"][0]["bars"]) == 2)

    removed = apply_edit(copied, {"op": "delete_bar", "bar": 1})
    both(removed, lambda score: len(score["tracks"][0]["bars"]) == 1)

    rough = apply_edit(base, {"op": "set_duration", "bar": 0, "beat": 0, "duration": 0.6, "dotted": False})
    # 0.6 is not a Guitar Pro duration; quantize snaps it onto the eighth grid first.
    rough["tracks"][0]["bars"][0]["beats"][0]["duration"] = 0.6
    for note in rough["tracks"][0]["bars"][0]["beats"][0]["notes"]:
        note["duration"] = 0.6
    quantized = apply_edit(rough, {"op": "quantize", "grid": 0.5})
    both(quantized, lambda score: abs(score["tracks"][0]["bars"][0]["beats"][0]["duration"] - 0.5) < 1e-6)

    moved = apply_edit(parse_jianpu("key C\ntime 4/4\n1\n"), {"op": "transpose", "semitones": 2})
    both(moved, lambda score: OPEN_MIDI[_note(score, 0, 0)["string"]] + _note(score, 0, 0)["fret"] == 62)


def test_pull_and_transpose_change_the_sounding_pitches():
    score = parse_ascii("e|--5--3--|\nB|--------|\nG|--------|\nD|--------|\nA|--------|\nE|--------|\n")
    score = apply_edit(score, {"op": "set_pull", "bar": 0, "beat": 0, "note": 0})
    parsed = score_from_gp5_bytes(score_to_gp5_bytes(score))
    assert parsed["tracks"][0]["bars"][0]["beats"][0]["notes"][0]["pull"] is True
    moved = apply_edit(parse_jianpu("key C\ntime 4/4\n1\n"), {"op": "transpose", "semitones": 2})
    from app.tab.fingering import OPEN_MIDI

    note = moved["tracks"][0]["bars"][0]["beats"][0]["notes"][0]
    assert OPEN_MIDI[note["string"]] + note["fret"] == 62
