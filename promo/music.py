"""Generates an original upbeat background track + transition whooshes for the promo.
Usage: python3 music.py out.wav
"""
import sys, wave
import numpy as np

SR = 44100
DUR = 22.0
BPM = 120
BEAT = 60 / BPM
BOUNDS = [3.4, 6.8, 10.3, 13.9, 17.0]
POPS = [0.15, 0.27, 1.3, 3.7, 4.7, 7.05, 8.7, 10.5, 10.8, 14.1, 14.3, 17.3, 17.5, 18.4, 18.8, 19.7]

n = int(SR * DUR)
t = np.arange(n) / SR
mix = np.zeros(n)
rng = np.random.default_rng(7)


def add(sig, at, gain=1.0):
    i = int(at * SR)
    j = min(n, i + len(sig))
    if i < n:
        mix[i:j] += sig[: j - i] * gain


def env(length, a=0.005, d=0.2):
    tt = np.arange(int(length * SR)) / SR
    return np.minimum(tt / a, 1) * np.exp(-tt / d)


def kick():
    tt = np.arange(int(0.35 * SR)) / SR
    f = 50 + 110 * np.exp(-tt * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)


def clap():
    tt = np.arange(int(0.2 * SR)) / SR
    nz = rng.standard_normal(len(tt))
    nz = np.diff(nz, prepend=0)
    return nz * np.exp(-tt * 25) * 0.35


def hat():
    tt = np.arange(int(0.06 * SR)) / SR
    nz = np.diff(rng.standard_normal(len(tt)), prepend=0)
    return nz * np.exp(-tt * 70) * 0.18


def note(freq, length, kind="pluck"):
    tt = np.arange(int(length * SR)) / SR
    if kind == "bass":
        s = np.sign(np.sin(2 * np.pi * freq * tt)) * 0.3 + np.sin(2 * np.pi * freq * tt) * 0.7
        return s * np.minimum(tt / 0.01, 1) * np.exp(-tt / 0.35)
    s = np.sin(2 * np.pi * freq * tt) + 0.4 * np.sin(2 * np.pi * 2 * freq * tt) + 0.15 * np.sin(2 * np.pi * 3 * freq * tt)
    return s * np.minimum(tt / 0.004, 1) * np.exp(-tt / 0.18)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


# chords: Am - F - C - G (one bar each = 4 beats)
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
BASS = [45, 41, 48, 43]

total_beats = int(DUR / BEAT)
for b in range(total_beats):
    at = b * BEAT
    bar = (b // 4) % 4
    end_section = at > 20.6
    if at < 0.4:  # short intro: no drums on very first hit
        pass
    if not end_section:
        add(kick(), at, 0.9)
        if b % 2 == 1:
            add(clap(), at, 0.9)
        add(hat(), at + BEAT / 2, 1.0)
        add(note(midi(BASS[bar]), BEAT * 0.9, "bass"), at, 0.32)
        add(note(midi(BASS[bar]), BEAT * 0.45, "bass"), at + BEAT * 0.75, 0.2)
    # arpeggio in 8ths
    ch = CHORDS[bar]
    for k in range(2):
        m = ch[(b * 2 + k) % 3] + 12
        add(note(midi(m), 0.4), at + k * BEAT / 2, 0.16 if not end_section else 0.1)

# final chord hit
for m in CHORDS[0]:
    add(note(midi(m), 1.6) * 1.0, 20.5, 0.18)
    add(note(midi(m + 12), 1.6), 20.5, 0.1)
add(kick(), 20.5, 1.0)


# whooshes at transitions (filtered noise swell)
def whoosh(length=0.9):
    m = int(length * SR)
    nz = rng.standard_normal(m)
    out = np.zeros(m)
    tt = np.arange(m) / SR
    cutoff = 0.02 + 0.25 * np.sin(np.pi * tt / length) ** 2
    y = 0.0
    for i in range(m):
        y += cutoff[i] * (nz[i] - y)
        out[i] = y
    return out * np.sin(np.pi * tt / length) ** 2 * 0.9


for bnd in BOUNDS:
    add(whoosh(), bnd - 0.5, 0.8)


# pops for elements appearing
def pop():
    tt = np.arange(int(0.08 * SR)) / SR
    f = 900 + 1400 * tt / 0.08
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 45)


for p in POPS:
    add(pop(), p, 0.22)

# master: fade out, soft clip, normalise
fade = np.clip((DUR - t) / 1.0, 0, 1)
mix *= fade
mix = np.tanh(mix * 1.2)
mix /= np.max(np.abs(mix)) + 1e-9
mix *= 0.89
stereo = np.stack([mix, np.roll(mix, 120) * 0.98], axis=1)

with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((stereo * 32767).astype(np.int16).tobytes())
print("wrote", sys.argv[1])
