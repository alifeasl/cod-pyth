"""Original cinematic/trap-style track for promo2: 808 sub, impacts on text slams,
riser into the logo reveal. Usage: python3 music2.py out.wav
"""
import sys, wave
import numpy as np

SR = 44100
DUR = 21.0
BPM = 100
BEAT = 60 / BPM
BOUNDS = [2.9, 7.2, 12.2, 14.8]
SLAMS = [0.25, 0.6, 1.45, 1.8]          # keep in sync with promo2.html
WORD_CUTS = [12.2 + 0.15 + i * 0.4 for i in range(6)]
LOGO = 14.8

n = int(SR * DUR)
t = np.arange(n) / SR
mix = np.zeros(n)
rng = np.random.default_rng(3)


def add(sig, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(sig))
    if 0 <= i < n:
        mix[i:j] += sig[: j - i] * g


def tt(sec):
    return np.arange(int(sec * SR)) / SR


def lp(x, a):
    y = np.zeros_like(x); s = 0.0
    for i in range(len(x)):
        s += a * (x[i] - s); y[i] = s
    return y


def sub808(freq, length):
    x = tt(length)
    f = freq * (1 + 1.5 * np.exp(-x * 40))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return np.tanh(s * 1.8) * np.minimum(x / .005, 1) * np.exp(-x / (length * .6))


def kick():
    x = tt(.3); f = 45 + 140 * np.exp(-x * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 10)


def snare():
    x = tt(.3)
    body = np.sin(2 * np.pi * 190 * x) * np.exp(-x * 30) * .5
    nz = np.diff(rng.standard_normal(len(x)), prepend=0) * np.exp(-x * 14) * .45
    return body + nz


def hat(open_=False):
    x = tt(.25 if open_ else .05)
    return np.diff(rng.standard_normal(len(x)), prepend=0) * np.exp(-x * (12 if open_ else 80)) * .14


def impact():
    x = tt(1.6)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 90 * np.exp(-x * 9)) / SR) * np.exp(-x * 2.6)
    nz = lp(rng.standard_normal(len(x)), .08) * np.exp(-x * 5) * 1.5
    return np.tanh((boom + nz) * 1.5)


def pad(freqs, length):
    x = tt(length); s = np.zeros_like(x)
    for f in freqs:
        for d in (-0.15, 0.15):
            s += np.sign(np.sin(2 * np.pi * (f + d) * x)) * 0.5 + np.sin(2 * np.pi * (f + d) * x)
    s = lp(s, .05)
    a = np.minimum(x / .4, 1) * np.minimum((length - x) / .4, 1)
    return s * a / len(freqs)


def bell(f, length=1.2):
    x = tt(length)
    s = np.sin(2 * np.pi * f * x) + .5 * np.sin(2 * np.pi * f * 2.76 * x) * np.exp(-x * 6)
    return s * np.exp(-x * 3)


def riser(length):
    x = tt(length)
    nz = rng.standard_normal(len(x))
    out = np.zeros_like(x); s = 0.0
    a = .01 + .35 * (x / length) ** 2
    for i in range(len(x)):
        s += a[i] * (nz[i] - s); out[i] = s
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * (x / length) ** 2) / SR) * .25
    return (out + tone) * (x / length) ** 2


def whoosh(length=.7):
    x = tt(length)
    return lp(rng.standard_normal(len(x)), .12) * np.sin(np.pi * x / length) ** 2


m = lambda k: 440 * 2 ** ((k - 69) / 12)

# --- intro: impacts on each slam, low drone ---
add(pad([m(38), m(45)], 2.9), 0, .35)
for s_ in SLAMS:
    add(impact(), s_ + 0.2, .55)

# --- beat from 2.9 to 14.8, half-time trap ---
CH = [[50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52]]   # Dm Bb Gm A
BASS = [38, 34, 31, 33]
start = 2.9
bars = int((LOGO - start) / (4 * BEAT)) + 1
for bar in range(bars):
    b0 = start + bar * 4 * BEAT
    ci = bar % 4
    add(pad([m(k) for k in CH[ci]], 4 * BEAT), b0, .22)
    add(sub808(m(BASS[ci]), BEAT * 1.6), b0, .55)
    add(sub808(m(BASS[ci]), BEAT * 1.0), b0 + 2.5 * BEAT, .45)
    for b in range(4):
        at = b0 + b * BEAT
        if at >= LOGO - .05:
            break
        if b in (0,):
            add(kick(), at, .9)
        if b == 2:
            add(snare(), at, .8)
        # hats: 8ths with rolls on last beat
        steps = 4 if b == 3 and bar % 2 == 1 else 2
        for h in range(steps):
            ah = at + h * BEAT / steps
            if ah < LOGO - .05:
                add(hat(), ah, 1.0)
    add(kick(), b0 + 2.75 * BEAT, .6) if b0 + 2.75 * BEAT < LOGO - .1 else None

# bell melody over steps section
mel = [74, 72, 69, 77, 76, 74, 72, 69]
for i, k in enumerate(mel):
    at = 7.2 + i * BEAT
    add(bell(m(k)), at, .12)

# word-cut hits
for w in WORD_CUTS:
    add(snare(), w, .35)
    add(hat(True), w, .8)

# whooshes into each scene
for b in BOUNDS:
    add(whoosh(), b - .55, .5)

# riser then big impact + chord on logo
add(riser(1.8), LOGO - 1.8, .5)
add(impact(), LOGO, 1.0)
add(pad([m(50), m(57), m(62), m(65)], DUR - LOGO), LOGO, .32)
for i, k in enumerate([62, 65, 69, 74]):
    add(bell(m(k), 2.0), LOGO + .9 + i * .25, .1)
# soft beat under the contact section
for i in range(int((DUR - 1.5 - LOGO - 1.2) / BEAT)):
    at = LOGO + 1.2 + i * BEAT
    add(hat(), at, .7)
    if i % 2 == 0:
        add(kick(), at, .5)

fade = np.clip((DUR - t) / 1.2, 0, 1) * np.clip(t / .05, 0, 1)
mix *= fade
mix = np.tanh(mix * 1.1)
mix /= np.max(np.abs(mix)) + 1e-9
mix *= .89
st = np.stack([mix, np.roll(mix, 90)], axis=1)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("wrote", sys.argv[1])
