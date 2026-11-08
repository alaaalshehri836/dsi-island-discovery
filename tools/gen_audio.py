"""Original music score + sound effects for DSI Island Part 1 (synthesised from scratch,
no samples -> no third-party licensing). Usage: python gen_audio.py ../assets/audio"""
import os, sys, subprocess, tempfile, numpy as np, soundfile as sf
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100
OUT = sys.argv[1]
rng = np.random.default_rng(42)

def t_(d): return np.arange(int(d * SR)) / SR
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x, axis=0)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x, axis=0)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x, axis=0)
def env(n, a, d, s, r, sus_len=None):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    sl = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, a, endpoint=False), np.linspace(1, s, d, endpoint=False), np.full(sl, s), np.linspace(s, 0, r)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]
def mtof(m): return 440 * 2 ** ((m - 69) / 12)

def reverb_ir(sec=2.6, decay=2.2, seed=1):
    r = np.random.default_rng(seed); n = int(sec * SR); t = np.arange(n) / SR
    ir = np.stack([r.standard_normal(n), r.standard_normal(n)], 1) * np.exp(-t * decay)[:, None]
    ir = lp(ir, 6000); ir[:int(0.012 * SR)] = 0
    return ir / np.sqrt((ir ** 2).sum(0))
IR = reverb_ir()
def reverb(x, wet=0.3):
    if x.ndim == 1: x = np.stack([x, x], 1)
    y = np.stack([fftconvolve(x[:, c], IR[:, c])[:len(x)] for c in range(2)], 1)
    return x * (1 - wet) + y * wet * 0.6

def pan(x, p):  # p -1..1
    return np.stack([x * np.sqrt((1 - p) / 2), x * np.sqrt((1 + p) / 2)], 1)

def place(buf, x, at):
    i = int(at * SR)
    if i >= len(buf): return
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += x[:n]

def save(name, x, br='160k', norm=0.89):
    x = x / (np.max(np.abs(x)) + 1e-9) * norm
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
        sf.write(tf.name, x.astype(np.float32), SR)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', tf.name, '-b:a', br, os.path.join(OUT, name)], check=True)
        os.unlink(tf.name)
    print(name, round(len(x) / SR, 2))

# ---------------------------------------------------------------- instruments
def kalimba(m, d=1.4, v=0.5):
    t = t_(d); f = mtof(m)
    x = (np.sin(2 * np.pi * f * t + 1.3 * np.exp(-t * 18) * np.sin(2 * np.pi * f * 3.0 * t)) * np.exp(-t * 3.2)
         + 0.18 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 14))
    return x * v * env(len(t), 0.002, 0.05, 1, 0.08)
def marimba(m, d=1.0, v=0.5):
    t = t_(d); f = mtof(m)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 4.5) + 0.35 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 20)
    return x * v * env(len(t), 0.003, 0.05, 1, 0.05)
def pad(ms, d, v=0.2, bright=1800, a=1.2, r=1.5):
    t = t_(d); x = np.zeros((len(t), 2))
    for m in ms:
        for det, p in ((-0.09, -0.6), (0.0, 0.0), (0.08, 0.6)):
            f = mtof(m + det)
            w = 2 * ((f * t + rng.random()) % 1) - 1   # saw
            x += pan(w, p)
    x = lp(x, bright, 2) * env(len(t), a, 0.5, 0.85, r)[:, None]
    return x * v / len(ms)
def flute(notes, v=0.3):
    """notes: list of (start, dur, midi) -> mono"""
    end = max(s + d for s, d, m in notes) + 1
    out = np.zeros(int(end * SR))
    for s, d, m in notes:
        t = t_(d + 0.4); f = mtof(m)
        vib = 1 + 0.005 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.4, 0, 1)
        ph = 2 * np.pi * f * np.cumsum(vib) / SR
        x = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
        br = bp(rng.standard_normal(len(t)), f * 0.8, min(f * 3, 18000)) * 0.12
        e = env(len(t), 0.09, 0.2, 0.8, 0.35)
        place(out, (x + br) * e * v, s)
    return out
def bass(m, d, v=0.4):
    t = t_(d); f = mtof(m)
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t * 3)
    return x * v * env(len(t), 0.01, 0.2, 0.7, 0.3)
def shaker(v=0.12):
    t = t_(0.12); x = hp(rng.standard_normal(len(t)), 5000) * np.exp(-t * 45)
    return x * v
def soft_tom(v=0.4, f0=90):
    t = t_(0.5); f = f0 * (1 + 0.6 * np.exp(-t * 30))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) * v
def bell(m, d=3.0, v=0.3):
    t = t_(d); f = mtof(m); x = np.zeros(len(t))
    for ratio, amp, dec in ((1, 1, 1.4), (2.76, 0.45, 2.8), (5.4, 0.25, 4.5), (8.9, 0.12, 7)):
        x += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t * dec)
    return x * v * env(len(t), 0.002, 0.1, 1, 0.3)
def riser(d=2.0, v=0.4):
    t = t_(d); n = rng.standard_normal(len(t))
    out = np.zeros(len(t)); k = t / d
    bands = [(200, 600), (500, 1500), (1200, 3500), (3000, 8000), (6000, 14000)]
    for j, (lo, hi) in enumerate(bands):
        w = np.clip(1 - np.abs(k * (len(bands) - 1) - j), 0, 1)
        out += bp(n, lo, hi) * w
    return out * (t / d) ** 2 * v

# ---------------------------------------------------------------- music cue (26.5 s), D major / B minor
DUR = 27.5
M = np.zeros((int(DUR * SR), 2))
BPM = 90; B = 60 / BPM
# Intro 0-3.2: low shimmering pad
M[:int(4.4 * SR)] += pad([50, 57, 64, 69], 4.4, 0.35, 900, a=1.6, r=1.4)
# Arrival 3.2-7.2: Dmaj9 / Gmaj7#11 with kalimba arps
chords = [(3.2, [50, 57, 62, 66, 69, 76], [62, 66, 69, 73, 76, 81]), (5.2, [43, 50, 59, 62, 66, 73], [59, 62, 66, 69, 73, 78]),
          (7.2, [47, 54, 59, 62, 66, 73], [59, 62, 66, 71, 74, 78]), (9.2, [43, 50, 55, 59, 62, 69], [55, 59, 62, 67, 69, 74]),
          (11.2, [45, 52, 57, 61, 64, 69], [57, 61, 64, 69, 73, 76])]
for st, pc, arp in chords:
    place(M, pad(pc[1:], 2.4, 0.28, 1600, a=0.6, r=0.9), st)
    place(M, pan(bass(pc[0] - 12 if pc[0] > 45 else pc[0], 2.0, 0.35), 0), st)
    for i in range(8):
        n = arp[[0, 2, 4, 5, 3, 1, 2, 4][i]]
        place(M, pan(kalimba(n, 1.2, 0.26 if i % 2 == 0 else 0.18), -0.3 + 0.6 * (i % 2)), st + i * B / 2 * 0.833)
# gentle shaker groove 3.2-13
s = 3.2
while s < 13.0:
    place(M, pan(shaker(0.07 if int((s - 3.2) / (B / 2)) % 2 else 0.11), 0.4), s); s += B / 2
for k in range(5):
    place(M, pan(soft_tom(0.28), -0.1), 7.2 + k * B * 2)
# exploration melody (flute) 7.2-13
mel = [(7.4, 0.55, 74), (8.0, 0.3, 76), (8.3, 0.9, 78), (9.4, 0.55, 81), (10.0, 0.3, 79), (10.3, 0.9, 78), (11.4, 0.5, 76), (11.95, 1.0, 73)]
place(M, pan(flute(mel, 0.16), 0.15), 0)
# Mystery 13-19.4: Bm(add9) - Gmaj7#11 - Em9 - F#sus, sparse, shimmering
myst = [(13.0, [47, 54, 61, 62, 66]), (14.6, [43, 54, 59, 61, 66]), (16.3, [40, 55, 59, 62, 66]), (17.8, [42, 54, 59, 61, 64])]
for st, pc in myst:
    place(M, pad(pc, 2.3, 0.3, 1200, a=0.8, r=1.0), st)
    place(M, pan(bass(pc[0] - 12 + 12 * (pc[0] < 44), 2.0, 0.32), 0), st)
for i, n in enumerate([78, 81, 85, 86, 85, 81, 78, 73, 78, 81, 85, 90]):
    place(M, pan(bell(n, 2.2, 0.07), -0.7 + 1.4 * ((i * 3) % 5) / 4), 13.1 + i * 0.5)
place(M, pan(riser(1.4, 0.5), 0), 13.2)   # build into the reveal at 14.6
# Finale 19.4-27: warm D major resolution
place(M, pad([50, 57, 62, 66, 69, 74, 78], 7.8, 0.5, 2400, a=0.25, r=3.5), 19.4)
place(M, pan(bass(38, 6.5, 0.45), 0), 19.4)
for i, n in enumerate([62, 66, 69, 74, 78, 81, 86]):
    place(M, pan(kalimba(n, 2.5, 0.22), -0.5 + i / 6), 19.45 + i * 0.12)
place(M, pan(bell(86, 4, 0.12), 0.2), 19.4); place(M, pan(bell(81, 4, 0.08), -0.3), 19.42)
place(M, pan(soft_tom(0.45, 70), 0), 19.4)
fin = [(20.4, 0.6, 78), (21.0, 0.6, 81), (21.6, 1.6, 83), (23.4, 0.6, 81), (24.0, 2.5, 78)]
place(M, pan(flute(fin, 0.14), -0.1), 0)
M = reverb(M, 0.35)
fade = int(2.2 * SR); M[-fade:] *= np.linspace(1, 0, fade)[:, None]
fi = int(0.4 * SR); M[:fi] *= np.linspace(0, 1, fi)[:, None]
os.makedirs(os.path.join(OUT, 'music'), exist_ok=True); os.makedirs(os.path.join(OUT, 'sfx'), exist_ok=True)
save('music/score_part1.mp3', M, '192k', 0.85)

# ---------------------------------------------------------------- loops (seamless via crossfade)
def make_loop(x, xf=1.0):
    n = int(xf * SR); a = x[:n]; b = x[-n:]
    w = np.linspace(0, 1, n)[:, None] if x.ndim > 1 else np.linspace(0, 1, n)
    y = x[n:].copy(); y[-n:] = b * (1 - w) + a * w
    return y
def ocean(d=14):
    n = int(d * SR); t = np.arange(n) / SR
    base = lp(np.cumsum(rng.standard_normal((n, 2)), 0) * 0.02, 900)
    base = hp(base, 40)
    hiss = bp(rng.standard_normal((n, 2)), 1500, 9000) * 0.5
    swell = np.zeros(n)
    for c in np.arange(0.5, d, 3.6):
        swell += np.exp(-((t - c - rng.uniform(-0.3, 0.3)) / 1.0) ** 2) * rng.uniform(0.7, 1.0)
    crash = np.zeros(n)
    for c in np.arange(1.1, d, 3.6):
        crash += np.clip(t - c, 0, None) ** 0.3 * np.exp(-np.clip(t - c, 0, None) * 1.6) * (t > c)
    x = base / np.max(np.abs(base)) * (0.35 + 0.5 * swell[:, None]) + hiss * (0.05 + 0.6 * crash[:, None])
    return make_loop(x, 1.5)
save('sfx/amb_ocean.mp3', ocean(), '128k', 0.8)
def wind(d=12):
    n = int(d * SR); t = np.arange(n) / SR
    x = rng.standard_normal((n, 2))
    m1 = (0.5 + 0.5 * np.sin(2 * np.pi * t / 5.3))[:, None]
    out = bp(x, 200, 700) * m1 + bp(x, 600, 1600) * (1 - m1) * 0.6
    amp = 0.5 + 0.35 * np.sin(2 * np.pi * t / 6) + 0.15 * np.sin(2 * np.pi * t / 1.7)
    out = lp(out * amp[:, None], 2500)
    return make_loop(out, 1.5)
save('sfx/amb_wind.mp3', wind(), '96k', 0.7)
def jungle(d=12):
    n = int(d * SR); out = np.zeros((n, 2)); t = np.arange(n) / SR
    ins = bp(rng.standard_normal(n), 5500, 7500) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * t) > 0.3) * 0.05
    out += pan(ins, 0.3)
    for k in range(14):  # bird chirps
        st = rng.uniform(0, d - 1); f0 = rng.uniform(2200, 4200); L = rng.uniform(0.06, 0.16)
        for rep in range(int(rng.integers(2, 5))):
            tt = t_(L); f = f0 * (1 + 0.35 * np.sin(np.pi * tt / L)) * rng.uniform(0.95, 1.05)
            ch = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / L) ** 2 * 0.25
            place(out, pan(ch, rng.uniform(-0.8, 0.8)), st + rep * (L + 0.05))
    return make_loop(reverb(out, 0.4), 1.0)
save('sfx/amb_jungle.mp3', jungle(), '96k', 0.6)
def portal_hum(d=10):
    n = int(d * SR); t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 55.6 * t) + 0.4 * np.sin(2 * np.pi * 110.3 * t)
         + 0.15 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t)))
    sh = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(0.1, 0.5) * t)) for f in (1318, 1661, 1976, 2637)) * 0.04
    y = np.stack([x * 0.5 + sh, x * 0.5 + np.roll(sh, 3000)], 1)
    return make_loop(reverb(y, 0.3), 1.0)
save('sfx/portal_hum.mp3', portal_hum(), '96k', 0.6)

# ---------------------------------------------------------------- one-shots
for i in range(4):
    t = t_(0.22)
    crunch = bp(rng.standard_normal(len(t)), 600 + i * 150, 4200) * np.exp(-t * 26)
    grains = (rng.random(len(t)) > 0.985) * rng.standard_normal(len(t)) * np.exp(-t * 18) * 0.8
    thump = np.sin(2 * np.pi * 80 * t) * np.exp(-t * 40) * 0.5
    save(f'sfx/step_sand_{i}.mp3', crunch * 0.6 + hp(grains, 2000) + thump, '96k', 0.7)
t = t_(1.6)
boat = (np.sin(2 * np.pi * np.cumsum(70 * (1 + 0.3 * np.exp(-t * 20))) / SR) * np.exp(-t * 6)
        + bp(rng.standard_normal(len(t)), 300, 2500) * np.exp(-t * 3) * 0.35 * (t > 0.05))
save('sfx/boat_land.mp3', reverb(boat, 0.15), '96k', 0.8)
t = t_(0.8)
splash = bp(rng.standard_normal(len(t)), 800, 8000) * (np.exp(-t * 8) * (1 - np.exp(-t * 60)))
save('sfx/splash.mp3', splash, '96k', 0.6)
t = t_(0.5); jump = soft_tom(0.6, 60)[:len(t)] + bp(rng.standard_normal(len(t)), 500, 5000) * np.exp(-t * 14) * 0.5
save('sfx/land_sand.mp3', jump, '96k', 0.7)
# portal reveal: deep swell + riser + bell cluster
rv = np.zeros((int(5.0 * SR), 2))
place(rv, pan(riser(1.6, 0.6), 0), 0)
t = t_(4.0); boom = np.sin(2 * np.pi * np.cumsum(45 + 20 * np.exp(-t * 3)) / SR) * env(len(t), 0.05, 0.6, 0.5, 2.5) * 0.9
place(rv, pan(boom, 0), 1.5)
for i, m in enumerate([74, 78, 81, 85, 90, 93]):
    place(rv, pan(bell(m, 3.2, 0.22), -0.6 + i * 0.24), 1.55 + i * 0.07)
save('sfx/portal_reveal.mp3', reverb(rv, 0.45), '160k', 0.85)
# startup chime (retro square arp + CRT whine)
st = np.zeros(int(2.2 * SR))
for i, m in enumerate([62, 69, 74, 78, 81]):
    tt = t_(0.5); f = mtof(m)
    sq = np.sign(np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 6) * 0.18
    place(st, lp(sq, 4000), 0.25 + i * 0.075)
tt = t_(0.35); place(st, np.sin(2 * np.pi * 15600 * tt) * np.exp(-tt * 9) * 0.02, 0)
save('sfx/startup.mp3', reverb(st, 0.35), '128k', 0.6)
t = t_(1.2); save('sfx/text_chime.mp3', reverb(bell(93, 1.2, 0.3) + bell(98, 1.2, 0.12), 0.4), '96k', 0.5)
t = t_(0.15); save('sfx/ui_click.mp3', np.sign(np.sin(2 * np.pi * 880 * t)) * np.exp(-t * 30) * 0.3, '96k', 0.5)
