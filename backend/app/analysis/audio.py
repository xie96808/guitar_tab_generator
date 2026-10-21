from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from scipy import signal
from scipy.io import wavfile

ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class AudioData:
    y: np.ndarray  # float32 mono [-1, 1]
    sr: int
    duration_s: float


def load_wav_mono(path: Path, target_sr: int = 22050) -> AudioData:
    sr, data = wavfile.read(str(path))
    x = data
    if hasattr(x, "ndim") and x.ndim > 1:
        x = x.mean(axis=1)

    if x.dtype.kind == "f":
        x = x.astype(np.float32)
        x = np.clip(x, -1.0, 1.0)
    elif x.dtype == np.int16:
        x = x.astype(np.float32) / 32768.0
    elif x.dtype == np.int32:
        x = x.astype(np.float32) / 2147483648.0
    elif x.dtype == np.uint8:
        x = (x.astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported WAV dtype: {x.dtype}")

    if sr != target_sr:
        gcd = math.gcd(sr, target_sr)
        up = target_sr // gcd
        down = sr // gcd
        x = signal.resample_poly(x, up=up, down=down).astype(np.float32)
        sr = target_sr

    x = np.clip(x, -1.0, 1.0).astype(np.float32)
    duration_s = float(len(x) / sr)
    return AudioData(y=x, sr=sr, duration_s=duration_s)


def stft_mag(y: np.ndarray, *, n_fft: int, hop: int) -> np.ndarray:
    win = signal.windows.hann(n_fft, sym=False).astype(np.float32)
    frames = []
    for i in range(0, max(1, len(y) - n_fft), hop):
        frame = y[i : i + n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft - len(frame)))
        X = np.fft.rfft(frame * win)
        frames.append(np.abs(X))
    return np.stack(frames, axis=1)  # (freq_bins, frames)


def hpss_masks(mag: np.ndarray, *, k_time: int = 17, k_freq: int = 17) -> tuple[np.ndarray, np.ndarray]:
    # Median-filter HPSS (Fitzgerald). Works reasonably well for pop mixes.
    if k_time % 2 == 0:
        k_time += 1
    if k_freq % 2 == 0:
        k_freq += 1
    harm = signal.medfilt(mag, kernel_size=(1, k_time))
    perc = signal.medfilt(mag, kernel_size=(k_freq, 1))
    denom = harm + perc + 1e-8
    return (harm / denom).astype(np.float32), (perc / denom).astype(np.float32)


def spectral_flux(onset_mag: np.ndarray) -> np.ndarray:
    diff = np.diff(onset_mag, axis=1)
    diff = np.maximum(diff, 0.0)
    flux = diff.sum(axis=0)
    flux = np.concatenate([[0.0], flux])
    flux = flux.astype(np.float32)
    if flux.max() > 0:
        flux /= flux.max()
    return flux


def autocorr_tempo(onset_env: np.ndarray, *, frame_hz: float, bpm_min: int = 60, bpm_max: int = 180) -> float:
    onset_env = onset_env - np.mean(onset_env)
    corr = signal.correlate(onset_env, onset_env, mode="full")
    corr = corr[len(corr) // 2 :]
    lags = np.arange(len(corr)) / frame_hz
    bpm = 60.0 / np.maximum(lags, 1e-9)
    mask = (bpm >= bpm_min) & (bpm <= bpm_max)
    corr2 = corr.copy()
    corr2[~mask] = -np.inf
    lag_idx = int(np.argmax(corr2))
    if not np.isfinite(corr2[lag_idx]) or lag_idx == 0:
        return 120.0
    return float(60.0 / (lags[lag_idx] + 1e-9))


def pick_beats(onset_env: np.ndarray, *, frame_hz: float, tempo_bpm: float) -> np.ndarray:
    period_s = 60.0 / max(tempo_bpm, 1e-6)
    period = max(1, int(round(period_s * frame_hz)))
    env = onset_env.astype(np.float32)
    n = len(env)
    best_phase = 0
    best_score = -1.0
    for phase in range(min(period, 2000)):
        idx = np.arange(phase, n, period)
        score = float(env[idx].sum()) if len(idx) else 0.0
        if score > best_score:
            best_score = score
            best_phase = phase
    beats = []
    for t in np.arange(best_phase, n, period):
        lo = max(0, int(t - period * 0.2))
        hi = min(n, int(t + period * 0.2) + 1)
        local = int(np.argmax(env[lo:hi])) + lo
        beats.append(local)
    beats = np.unique(np.array(beats, dtype=int))
    return beats / frame_hz


def peak_onsets(onset_env: np.ndarray, *, frame_hz: float, min_separation_s: float = 0.06) -> np.ndarray:
    distance = max(1, int(round(min_separation_s * frame_hz)))
    peaks, _ = signal.find_peaks(onset_env, height=0.2, distance=distance)
    return peaks.astype(np.float32) / frame_hz


def chroma_from_stft(mag: np.ndarray, *, sr: int, n_fft: int) -> np.ndarray:
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    chroma = np.zeros((12, mag.shape[1]), dtype=np.float32)
    eps = 1e-8
    for bin_idx, f in enumerate(freqs):
        if f < 55.0 or f > 5000.0:
            continue
        midi = 69.0 + 12.0 * np.log2((f + eps) / 440.0)
        nearest = float(np.round(midi))
        pc = int(nearest) % 12
        detune = float(midi - nearest)
        w = float(np.exp(-0.5 * (detune / 0.35) ** 2))
        # De-emphasize very high bins and some harmonic noise.
        w *= float(1.0 / (1.0 + (f / 2000.0) ** 2))
        chroma[pc] += (mag[bin_idx].astype(np.float32) * w)
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-6)
    return chroma


def sync_to_beats(feature: np.ndarray, beat_times: np.ndarray, *, frame_hz: float) -> np.ndarray:
    n_frames = feature.shape[1]
    frame_times = np.arange(n_frames, dtype=np.float32) / frame_hz
    beat_feat = []
    for i in range(len(beat_times)):
        t0 = beat_times[i]
        t1 = beat_times[i + 1] if i + 1 < len(beat_times) else frame_times[-1] + 1e-6
        mask = (frame_times >= t0) & (frame_times < t1)
        if not np.any(mask):
            beat_feat.append(np.zeros((feature.shape[0],), dtype=np.float32))
        else:
            beat_feat.append(feature[:, mask].mean(axis=1))
    return np.stack(beat_feat, axis=1)


def analyze_primitives(path: Path, progress: ProgressCb) -> dict:
    progress(5, "Loading audio (WAV)…")
    audio = load_wav_mono(path)
    progress(10, "Computing onset features…")
    n_fft = 4096
    hop = 512
    mag = stft_mag(audio.y, n_fft=n_fft, hop=hop)
    mag = np.log1p(mag).astype(np.float32)
    hmask, pmask = hpss_masks(mag, k_time=17, k_freq=17)
    mag_h = mag * hmask
    mag_p = mag * pmask
    frame_hz = audio.sr / hop
    onset_env = spectral_flux(mag_p)
    onset_env = signal.medfilt(onset_env, kernel_size=9).astype(np.float32)
    if onset_env.max() > 0:
        onset_env /= onset_env.max()

    progress(25, "Estimating tempo & beats…")
    tempo = autocorr_tempo(onset_env, frame_hz=frame_hz)
    beats = pick_beats(onset_env, frame_hz=frame_hz, tempo_bpm=tempo)
    onsets = peak_onsets(onset_env, frame_hz=frame_hz)

    progress(45, "Estimating chroma…")
    chroma = chroma_from_stft(mag_h, sr=audio.sr, n_fft=n_fft)
    chroma_beat = sync_to_beats(chroma, beats, frame_hz=frame_hz)

    return {
        "audio": {"sr": audio.sr, "duration_s": audio.duration_s},
        "tempo_bpm": tempo,
        "beat_times": beats.tolist(),
        "onset_times": onsets.tolist(),
        "chroma_beat": chroma_beat.tolist(),
    }
