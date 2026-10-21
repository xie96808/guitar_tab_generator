from __future__ import annotations

import io
import struct
from typing import Any, Optional
from xml.etree import ElementTree

from .fingering import finger_beats
from .gp5 import score_from_gp5_bytes

CHORD_PITCHES = {
    "Em": [40, 47, 52, 55, 59, 64],
    "G": [43, 47, 50, 55, 59, 67],
    "C": [48, 52, 55, 60, 64],
    "D": [50, 57, 62, 66],
    "Am": [40, 45, 52, 57, 60, 64],
    "E": [40, 47, 52, 56, 59, 64],
    "A": [40, 45, 52, 57, 61, 64],
}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
KEY_ROOT = {"C": 60, "G": 67, "D": 62, "A": 69, "E": 64, "F": 65, "Am": 57, "Em": 52, "Dm": 50}
ASCII_STRINGS = {"e": 1, "B": 2, "G": 3, "D": 4, "A": 5, "E": 6}


def empty_score(title: str = "Untitled") -> dict[str, Any]:
    return {
        "title": title,
        "tempo": 120,
        "timeSignature": "4/4",
        "keySignature": "C",
        "tracks": [
            {
                "name": "Guitar",
                "tuning": [64, 59, 55, 50, 45, 40],
                "bars": [{"repeatStart": False, "repeatEnd": -1, "beats": [{"duration": 1, "rest": True, "notes": []}]}],
            }
        ],
    }


def pack_beats(beats: list[dict[str, Any]], time_signature: str) -> list[dict[str, Any]]:
    numerator, denominator = time_signature.split("/")
    capacity = int(numerator) * 4.0 / int(denominator)
    packed: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    filled = 0.0
    for beat in beats:
        duration = float(beat["duration"])
        if current and filled + duration > capacity + 1e-6:
            packed.append(current)
            current = []
            filled = 0.0
        current.append(beat)
        filled += duration
        if filled + 1e-6 >= capacity:
            packed.append(current)
            current = []
            filled = 0.0
    if current:
        packed.append(current)
    if not packed:
        packed = [[{"duration": 1, "rest": True, "notes": []}]]
    return [{"repeatStart": False, "repeatEnd": -1, "beats": bar} for bar in packed]


def _score_from_bar_groups(
    title: str,
    time_signature: str,
    key: str,
    groups: list[list[list[int]]],
    duration: float,
    names: Optional[list[list[str]]] = None,
) -> dict[str, Any]:
    bars: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        fingered = finger_beats(group)
        beats = []
        for note_index, notes in enumerate(fingered):
            beat = {
                "duration": duration,
                "rest": False,
                "notes": [
                    {"string": note.string, "fret": note.fret, "duration": duration, "dynamic": "f"}
                    for note in notes
                ],
            }
            if names is not None:
                beat["chord"] = names[index][note_index]
            beats.append(beat)
        bars.extend(pack_beats(beats, time_signature))
    return {
        "title": title,
        "tempo": 120,
        "timeSignature": time_signature,
        "keySignature": key,
        "tracks": [{"name": "Guitar", "tuning": [64, 59, 55, 50, 45, 40], "bars": bars}],
    }


def parse_jianpu(text: str) -> dict[str, Any]:
    key = "C"
    meter = "4/4"
    body: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("key"):
            key = line.split()[-1]
        elif lowered.startswith("time") or lowered.startswith("meter"):
            meter = line.split()[-1]
        else:
            body.append(line)
    groups: list[list[list[int]]] = []
    has_barline = any("|" in line for line in body)
    chunks: list[list[int]] = []
    for line in body:
        pieces = line.split("|") if "|" in line else [line]
        for piece in pieces:
            degrees = [int(token) for token in piece.split() if token in list("1234567")]
            if degrees:
                chunks.append(degrees)
    if not has_barline:
        chunks = [[degree for group in chunks for degree in group]]
    root = KEY_ROOT[key]
    for degrees in chunks:
        groups.append([[root + MAJOR[degree - 1]] for degree in degrees])
    return _score_from_bar_groups("Jianpu", meter, key, groups, 1.0)


def parse_chords(text: str, strum: str = "quarter") -> dict[str, Any]:
    duration = 0.5 if strum == "eighth" else 1.0
    has_barline = any("|" in line for line in text.splitlines())
    groups: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("strum"):
            if line.lower().startswith("strum"):
                duration = 0.5 if "eighth" in line.lower() else 1.0
            continue
        pieces = line.split("|") if "|" in line else [line]
        for piece in pieces:
            found = [token for token in piece.split() if token in CHORD_PITCHES]
            if found:
                groups.append(found)
    if not has_barline and groups:
        groups = [[name for group in groups for name in group]]
    return _score_from_bar_groups(
        "Chords",
        "4/4",
        "C",
        [[CHORD_PITCHES[name] for name in group] for group in groups],
        duration,
        names=groups,
    )


def parse_ascii(text: str) -> dict[str, Any]:
    rows: list[tuple[int, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "|" not in line:
            continue
        name, body = line.split("|", 1)
        label = name.strip()
        string = ASCII_STRINGS[label]
        rows.append((string, body.replace("|", "")))
    width = max(len(body) for _, body in rows)
    events: list[list[tuple[int, int]]] = []
    index = 0
    while index < width:
        span = 1
        found: list[tuple[int, int]] = []
        for string, body in rows:
            if index < len(body) and body[index].isdigit():
                fret_text = body[index]
                if index + 1 < len(body) and body[index + 1].isdigit():
                    fret_text += body[index + 1]
                    span = max(span, 2)
                found.append((string, int(fret_text)))
        if found:
            events.append(found)
            index += span
        else:
            index += 1
    beats = []
    for event in events:
        beats.append(
            {
                "duration": 1.0,
                "rest": False,
                "notes": [
                    {"string": string, "fret": fret, "duration": 1.0, "dynamic": "f"}
                    for string, fret in sorted(event, key=lambda item: item[0])
                ],
            }
        )
    score = empty_score("ASCII")
    score["tracks"][0]["bars"][0]["beats"] = beats
    return score


def _read_varlen(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[index]
        index += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, index


def parse_midi(data: bytes) -> dict[str, Any]:
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    header_len = struct.unpack(">I", data[4:8])[0]
    division = struct.unpack(">H", data[12:14])[0]
    index = 8 + header_len
    if data[index : index + 4] != b"MTrk":
        raise ValueError("missing MIDI track")
    track_len = struct.unpack(">I", data[index + 4 : index + 8])[0]
    index += 8
    end = index + track_len
    tick = 0
    status = 0
    open_notes: dict[int, int] = {}
    sounded: list[tuple[int, int, int]] = []
    while index < end:
        delta, index = _read_varlen(data, index)
        tick += delta
        if data[index] & 0x80:
            status = data[index]
            index += 1
        if status == 0xFF:
            meta = data[index]
            index += 1
            length, index = _read_varlen(data, index)
            index += length
            continue
        if status & 0xF0 in (0xC0, 0xD0):
            index += 1
            continue
        data1 = data[index]
        data2 = data[index + 1]
        index += 2
        if status & 0xF0 == 0x90 and data2 > 0:
            open_notes[data1] = tick
        elif status & 0xF0 in (0x80, 0x90):
            start = open_notes.pop(data1, None)
            if start is not None and tick > start:
                sounded.append((data1, start, tick - start))
    sounded.sort(key=lambda item: (item[1], item[0]))
    if not sounded:
        return empty_score("MIDI")
    quarter = division or 480
    groups: list[list[tuple[int, int, int]]] = []
    for item in sounded:
        if groups and abs(groups[-1][0][1] - item[1]) <= quarter // 8:
            groups[-1].append(item)
        else:
            groups.append([item])
    beats = []
    for group in groups:
        duration_ticks = min(note[2] for note in group)
        quarters = max(0.5, round((duration_ticks / quarter) * 2) / 2)
        fingered = finger_beats([[note[0] for note in group]])[0]
        beats.append(
            {
                "duration": quarters,
                "rest": False,
                "notes": [
                    {"string": note.string, "fret": note.fret, "duration": quarters, "dynamic": "f"} for note in fingered
                ],
            }
        )
    score = empty_score("MIDI")
    score["tracks"][0]["bars"][0]["beats"] = beats
    return score


def midi_file(notes: list[tuple[int, int, int]], division: int = 480) -> bytes:
    """notes are (midi, start_tick, duration_ticks)."""
    events: list[tuple[int, bytes]] = []
    for midi, start, duration in notes:
        events.append((start, bytes([0x90, midi, 80])))
        events.append((start + duration, bytes([0x80, midi, 0])))
    events.sort(key=lambda item: item[0])
    track = bytearray()
    last = 0
    for tick, payload in events:
        delta = tick - last
        last = tick
        buffer = bytearray()
        while True:
            buffer.append(delta & 0x7F)
            delta >>= 7
            if delta == 0:
                break
        for index, byte in enumerate(reversed(buffer)):
            track.append(byte | (0x80 if index < len(buffer) - 1 else 0))
        track.extend(payload)
    track.extend(b"\x00\xff\x2f\x00")
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, division)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def parse_musicxml(xml: str) -> dict[str, Any]:
    root = ElementTree.fromstring(xml)
    pitches: list[int] = []
    durations: list[float] = []
    divisions = 1
    for element in root.iter():
        if element.tag.endswith("divisions") and element.text:
            divisions = int(element.text)
    for note in root.iter():
        if not note.tag.endswith("note"):
            continue
        if any(child.tag.endswith("rest") for child in note):
            continue
        step = octave = None
        alter = 0
        duration = divisions
        for child in note.iter():
            if child.tag.endswith("step") and child.text:
                step = child.text
            elif child.tag.endswith("octave") and child.text:
                octave = int(child.text)
            elif child.tag.endswith("alter") and child.text:
                alter = int(child.text)
            elif child.tag.endswith("duration") and child.text and duration == divisions:
                duration = int(child.text)
        if step is None or octave is None:
            continue
        midi = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step] + alter + 12 * (octave + 1)
        pitches.append(midi)
        durations.append(max(0.5, round((duration / divisions) * 2) / 2))
    if not pitches:
        return empty_score("MusicXML")
    fingered = finger_beats([[pitch] for pitch in pitches])
    beats = []
    for notes, duration in zip(fingered, durations):
        beats.append(
            {
                "duration": duration,
                "rest": False,
                "notes": [
                    {"string": note.string, "fret": note.fret, "duration": duration, "dynamic": "f"} for note in notes
                ],
            }
        )
    score = empty_score("MusicXML")
    score["tracks"][0]["bars"][0]["beats"] = beats
    return score


def parse_gp5(data: bytes) -> dict[str, Any]:
    return score_from_gp5_bytes(data)


def read_draft_file(name: str, data: bytes) -> dict[str, Any]:
    lowered = name.lower()
    if lowered.endswith((".gp5", ".gp")):
        return parse_gp5(data)
    if lowered.endswith((".xml", ".musicxml")):
        return parse_musicxml(data.decode("utf-8"))
    if lowered.endswith((".mid", ".midi")):
        return parse_midi(data)
    raise ValueError(f"unsupported draft file {name}")
