from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Guitar Pro string numbers: 1 is the high E, 6 is the low E.
OPEN_MIDI = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}
MAX_FRET = 22
MAX_SPAN = 4


@dataclass(frozen=True)
class FretNote:
    string: int
    fret: int

    @property
    def midi(self) -> int:
        return OPEN_MIDI[self.string] + self.fret


def _placements(midi: int) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for string, open_midi in OPEN_MIDI.items():
        fret = midi - open_midi
        if 0 <= fret <= MAX_FRET:
            found.append((string, fret))
    return found


def _enumerate(pitches: list[int]) -> list[tuple[FretNote, ...]]:
    results: list[tuple[FretNote, ...]] = []

    def walk(index: int, used: set[int], acc: list[FretNote]) -> None:
        if index == len(pitches):
            frets = [note.fret for note in acc]
            if max(frets) - min(frets) <= MAX_SPAN:
                ordered = tuple(sorted(acc, key=lambda note: -note.string))
                results.append(ordered)
            return
        for string, fret in _placements(pitches[index]):
            if string in used:
                continue
            used.add(string)
            acc.append(FretNote(string=string, fret=fret))
            walk(index + 1, used, acc)
            acc.pop()
            used.remove(string)

    if not pitches:
        raise ValueError("a beat needs at least one pitch")
    walk(0, set(), [])
    if not results:
        raise ValueError(f"no playable fingering within {MAX_SPAN} frets for {pitches}")
    return results


def _emission(notes: tuple[FretNote, ...]) -> float:
    frets = [note.fret for note in notes]
    return float(sum(frets) * 10 + (max(frets) - min(frets)))


def _min_pressed(notes: tuple[FretNote, ...]) -> Optional[int]:
    pressed = [note.fret for note in notes if note.fret >= 1]
    if not pressed:
        return None
    return min(pressed)


def _transition(left: tuple[FretNote, ...], right: tuple[FretNote, ...]) -> float:
    left_pos = _min_pressed(left)
    right_pos = _min_pressed(right)
    if left_pos is None or right_pos is None:
        return 0.0
    gap = abs(left_pos - right_pos)
    if gap > 4:
        return 100.0 + gap
    return gap * 0.05


def finger_beats(beats: list[list[int]]) -> list[list[FretNote]]:
    """Viterbi over playable fingerings. Standard tuning, 6 strings, span <= 4."""
    options = [_enumerate(list(pitches)) for pitches in beats]
    if not options:
        return []

    dp: list[list[float]] = [[_emission(choice) for choice in options[0]]]
    back: list[list[int]] = [[-1] * len(options[0])]
    for time in range(1, len(options)):
        previous = dp[-1]
        current_dp: list[float] = []
        current_back: list[int] = []
        for choice in options[time]:
            best_score: Optional[float] = None
            best_index = 0
            for index, earlier in enumerate(options[time - 1]):
                score = previous[index] + _transition(earlier, choice)
                if best_score is None or score < best_score:
                    best_score = score
                    best_index = index
            current_dp.append(float(best_score) + _emission(choice))
            current_back.append(best_index)
        dp.append(current_dp)
        back.append(current_back)

    chosen = [0] * len(options)
    chosen[-1] = min(range(len(dp[-1])), key=lambda index: dp[-1][index])
    for time in range(len(options) - 1, 0, -1):
        chosen[time - 1] = back[time][chosen[time]]
    return [list(options[time][chosen[time]]) for time in range(len(options))]
