"""Procedural pixel-art environment + portal assets for DSI Island."""
import json, os, sys, math, numpy as np
from PIL import Image, ImageDraw
from sdf import Prim, render, rot_x, rot_y, rot_z, hexc

rng = np.random.default_rng(7)
def H(h): return tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))

def outline(img, col='#14201a', diag=False):
    a = img[..., 3] > 0
    p = np.pad(a, 1)
    nb = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    if diag:
        nb |= p[:-2, :-2] | p[2:, 2:] | p[:-2, 2:] | p[2:, :-2]
    o = nb & ~a
    img = img.copy(); img[o, :3] = H(col); img[o, 3] = 255
    return img

def blank(w, h): return np.zeros((h, w, 4), np.uint8)

def put(img, x, y, col, a=255):
    h, w = img.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        img[y, x, :3] = col; img[y, x, 3] = a

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

def shade_blobs(w, h, blobs, ramp, light=(-0.6, -0.8), noise=0.18, seed=0, texture=True):
    """blobs: list of (cx, cy, r). Each blob shaded as a sphere lit from `light`; dithered tones."""
    img = blank(w, h); r_ = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    tex = r_.random((h, w))
    for (cx, cy, r) in blobs:
        dx = (xx + 0.5 - cx) / r; dy = (yy + 0.5 - cy) / r
        d2 = dx * dx + dy * dy
        # bumpy edge
        ang = np.arctan2(dy, dx)
        edge = 1 + 0.12 * np.sin(ang * 7 + cx) + 0.08 * np.sin(ang * 13 + cy)
        inside = d2 < edge ** 2
        nz = np.sqrt(np.clip(1 - d2, 0, 1))
        lum = (-dx * light[0] - dy * light[1]) * 0.6 + nz * 0.5
        if texture:
            lum = lum + (tex - 0.5) * noise * 2
        lum = lum + (BAYER[yy % 4, xx % 4] - 0.5) * 0.18
        idx = np.clip(((lum + 0.25) / 1.1 * len(ramp)).astype(int), 0, len(ramp) - 1)
        cols = np.array([H(c) for c in ramp])[idx]
        img[inside, :3] = cols[inside]; img[inside, 3] = 255
    return img

ASSETS = {}
def add(name, img, anchor=None):
    h, w = img.shape[:2]
    ASSETS[name] = (img, anchor if anchor is not None else (w // 2, h - 1))

# ------------------------------------------------------------------ palms
TRUNK = ['#4a2e1c', '#6e4a2c', '#98703f', '#bf9558']
FROND = ['#123d26', '#1d5a32', '#2f7d3c', '#4fa046', '#86c85a']
def palm(lean, height, nfr, phase, seed, sway):
    w, h = 150, height + 50
    img = blank(w, h)
    bx, by = w // 2 - int(lean * 0.4), h - 1
    tx, ty = bx + lean, by - height
    pts = []
    for i in range(height + 1):
        t = i / height
        x = bx + (tx - bx) * t + math.sin(t * math.pi) * lean * 0.35 * (1 if lean >= 0 else 1)
        y = by - height * t
        pts.append((x, y))
    for i, (x, y) in enumerate(pts):
        t = i / height
        wdt = 4.2 - 1.6 * t
        band = (int((by - y)) % 5) == 0
        for dx in range(-int(wdt) - 1, int(wdt) + 2):
            xx = int(round(x + dx)); yy = int(round(y))
            if abs(dx) > wdt: continue
            k = (dx + wdt) / (2 * wdt)
            ci = 3 if k < 0.25 else 2 if k < 0.6 else 1 if k < 0.85 else 0
            if band: ci = max(0, ci - 1)
            put(img, xx, yy, H(TRUNK[ci]))
    # fronds
    r_ = np.random.default_rng(seed)
    angs = np.linspace(-185, 5, nfr) + r_.uniform(-8, 8, nfr)
    order = sorted(range(nfr), key=lambda i: abs(angs[i] + 90) * -1)
    cx, cy = tx, ty
    for oi, i in enumerate(order):
        a0 = math.radians(angs[i])
        L = 40 + r_.uniform(0, 16) * (0.6 + 0.4 * abs(math.cos(a0)))
        swing = sway * math.sin(phase * 2 * math.pi + i * 0.7) * (0.6 + 0.4 * abs(math.cos(a0)))
        depth = oi / max(1, nfr - 1)
        prev = None
        steps = int(L)
        for s in range(steps):
            t = s / L
            ang = a0 + math.radians(swing) * t
            droop = 26 * t * t * (0.5 + 0.5 * abs(math.cos(a0)))
            x = cx + math.cos(ang) * L * t * 1.05
            y = cy + math.sin(ang) * L * t * 0.75 + droop + 2
            colr = FROND[min(4, 1 + int(depth * 2.6 + (1 - t) * 0.8))]
            put(img, int(round(x)), int(round(y)), H(FROND[0 if depth < 0.3 else 1]))
            # leaflets hang downward / outward
            if s > 2 and s % 1 == 0:
                ll = int(11 * math.sin(t * math.pi) + 2)
                side = 1 if math.cos(ang) >= 0 else -1
                for k in range(1, ll):
                    lx = int(round(x + side * k * 0.35)); ly = int(round(y + k))
                    tone = 2 + int(depth * 2.2) - (1 if k > ll * 0.6 else 0)
                    put(img, lx, ly, H(FROND[max(0, min(4, tone))]))
                    lx2 = int(round(x - side * k * 0.25)); ly2 = int(round(y + k * 0.7))
                    put(img, lx2, ly2, H(FROND[max(0, min(4, tone - 1))]))
                    put(img, lx + 1, ly, H(FROND[max(0, min(4, tone))]))
                    if k < 3: put(img, int(round(x)), int(round(y)) - 1, H(FROND[min(4, tone + 1)]))
    # coconuts
    for (ox, oy) in ((-2, 3), (2, 4), (0, 5)):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if abs(dx) + abs(dy) < 2:
                    put(img, cx + ox + dx, cy + oy + dy, H('#5a3a1c' if dx + dy > 0 else '#8a5a2a'))
    img = outline(img, '#0e2416')
    return img, (bx, by)

PALMS = [(-14, 92, 15, 1), (10, 104, 16, 2), (22, 80, 14, 3), (-4, 116, 17, 4)]
for vi, (lean, hh, nf, sd) in enumerate(PALMS):
    for f in range(6):
        im, anc = palm(lean, hh, nf, f / 6, sd, 6)
        add(f'palm{vi}_{f}', im, anc)

# ------------------------------------------------------------------ jungle trees / bushes
LEAF = ['#0b2a1e', '#123f27', '#1c5a32', '#2e7a3a', '#4f9c42', '#7cbf52']
LEAF_DARK = ['#071a14', '#0c2b1e', '#133d27', '#1d5530', '#2d6e36']
def jungle_tree(seed, w=130, h=170):
    r_ = np.random.default_rng(seed)
    img = blank(w, h)
    # trunk with roots
    cx = w // 2
    for y in range(h - 1, 40, -1):
        t = (h - y) / h
        wd = 5 + (8 if y > h - 10 else 0) * ((y - (h - 10)) / 10 if y > h - 10 else 0)
        for dx in range(-int(wd), int(wd) + 1):
            k = (dx + wd) / (2 * wd + 1e-6)
            ci = 2 if k < 0.3 else 1 if k < 0.7 else 0
            put(img, cx + dx + int(2 * math.sin(y * 0.05)), y, H(['#2a1a12', '#4a3020', '#6e4a30'][ci]))
    blobs = []
    for i in range(16):
        a = r_.uniform(0, 2 * math.pi); d = r_.uniform(0, 1) ** 0.6
        blobs.append((cx + math.cos(a) * d * 42, 62 + math.sin(a) * d * 34 - r_.uniform(0, 8), r_.uniform(14, 24)))
    blobs.sort(key=lambda b: b[1])
    can = shade_blobs(w, h, blobs, LEAF, seed=seed, noise=0.22)
    m = can[..., 3] > 0
    img[m] = can[m]
    # hanging vines
    for i in range(6):
        x = int(cx + r_.uniform(-40, 40)); y0 = int(70 + r_.uniform(0, 20)); L = int(r_.uniform(20, 50))
        for y in range(y0, min(h - 5, y0 + L)):
            if img[y, x, 3] == 0 or y > y0 + 8:
                put(img, x + int(math.sin(y * 0.3) * 0.8), y, H('#2e6a34' if y % 3 else '#4f9c42'))
    return outline(img, '#06140e')
add('jtree0', jungle_tree(11)); add('jtree1', jungle_tree(23)); add('jtree2', jungle_tree(37, 110, 150))

def bush(seed, w=56, h=36, ramp=LEAF, n=6):
    r_ = np.random.default_rng(seed)
    blobs = [(w / 2 + r_.uniform(-w * 0.3, w * 0.3), h - 10 - r_.uniform(0, h * 0.4), r_.uniform(8, 13)) for _ in range(n)]
    img = shade_blobs(w, h, blobs, ramp, seed=seed, noise=0.25)
    img[h - 2:, :, :] = 0
    return outline(img, '#06140e')
add('bush0', bush(3)); add('bush1', bush(5, 70, 40, n=8)); add('bushdark', bush(9, 64, 40, LEAF_DARK, 7))

def fern(seed, w=60, h=44, ramp=None, flowers=None):
    ramp = ramp or ['#123f27', '#1f6234', '#36873f', '#62ac4c', '#9bd062']
    r_ = np.random.default_rng(seed)
    img = blank(w, h); bx, by = w // 2, h - 2
    n = 9
    for i in range(n):
        a = math.radians(-165 + 150 * i / (n - 1) + r_.uniform(-6, 6))
        L = r_.uniform(18, 26) * (0.7 + 0.3 * math.sin(math.radians(-a * 180 / math.pi)))
        for s in range(int(L)):
            t = s / L
            x = bx + math.cos(a) * L * t
            y = by + math.sin(a) * L * t * 0.95 + 14 * t * t
            tone = 1 + int((1 - abs(i - n / 2) / (n / 2)) * 2.4)
            put(img, int(x), int(y), H(ramp[min(4, tone)]))
            ll = int(4 * math.sin(t * math.pi)) + 1
            for k in range(1, ll):
                put(img, int(x + k * 0.5), int(y + k * 0.6), H(ramp[min(4, tone + (1 if k == 1 else 0))]))
                put(img, int(x - k * 0.5), int(y + k * 0.6), H(ramp[max(0, tone - 1)]))
    if flowers:
        for _ in range(5):
            fx = int(bx + r_.uniform(-18, 18)); fy = int(by - r_.uniform(8, 20))
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                put(img, fx + dx, fy + dy, H(flowers[0] if (dx, dy) != (0, 0) else flowers[1]))
    return outline(img, '#071a10')
add('fern0', fern(1)); add('fern1', fern(2, 70, 50)); add('fernflower', fern(4, 60, 44, flowers=('#e8505c', '#ffd25a')))
add('fernflower2', fern(6, 60, 44, flowers=('#f4a03c', '#fff0a0')))

def monstera(seed, w=64, h=56):
    r_ = np.random.default_rng(seed)
    img = blank(w, h); bx, by = w // 2, h - 1
    ramp = ['#0d3322', '#175236', '#257042', '#3d9150', '#6cb860']
    for i in range(6):
        a = math.radians(-160 + 140 * i / 5 + r_.uniform(-10, 10))
        L = r_.uniform(22, 30)
        ex, ey = bx + math.cos(a) * L, by + math.sin(a) * L * 0.9
        # stem
        for s in range(int(L * 0.6)):
            t = s / L; put(img, int(bx + (ex - bx) * t), int(by + (ey - by) * t), H(ramp[1]))
        lr = r_.uniform(8, 11)
        for yy in range(-int(lr), int(lr) + 1):
            for xx in range(-int(lr * 1.2), int(lr * 1.2) + 1):
                if (xx / (lr * 1.2)) ** 2 + (yy / lr) ** 2 < 1:
                    ang = math.atan2(yy, xx)
                    if (int((ang + 3.2) * 2.6) % 2 == 0) and (xx * xx + yy * yy) > lr * lr * 0.45:
                        continue  # monstera slits
                    tone = 3 if (xx + yy) < -lr * 0.3 else 2 if (xx + yy) < lr * 0.5 else 1
                    if abs(xx) < 1: tone = 1
                    put(img, int(ex + xx), int(ey + yy), H(ramp[tone]))
    return outline(img, '#06140e')
add('monstera0', monstera(3)); add('monstera1', monstera(8, 72, 60))

def grass(seed, w=24, h=14):
    r_ = np.random.default_rng(seed); img = blank(w, h)
    ramp = ['#2f6b2e', '#4f8f38', '#7fb04a', '#b4cf6a']
    for i in range(14):
        x = r_.uniform(2, w - 2); L = r_.uniform(5, h - 1); lean = r_.uniform(-0.5, 0.5)
        for s in range(int(L)):
            put(img, int(x + lean * s), h - 1 - s, H(ramp[min(3, int(s / L * 4))]))
    return img
add('grass0', grass(1)); add('grass1', grass(2, 30, 16)); add('beachgrass', grass(3, 26, 18))

# ------------------------------------------------------------------ SDF props
STONE = {'stone': [hexc(c) for c in ['#2e2f3d', '#4d5063', '#767b8f', '#a2a8b8']],
         'moss': [hexc(c) for c in ['#1c3a22', '#2d5a2e', '#4b8040', '#78a854']],
         'rock': [hexc(c) for c in ['#3a3530', '#5e5850', '#8a8478', '#b8b2a2']],
         'wood': [hexc(c) for c in ['#3a2414', '#5e3c20', '#8a5e34', '#b4844a']],
         'wooddk': [hexc(c) for c in ['#24160c', '#3a2414', '#5e3c20', '#7a5230']],
         'iron': [hexc(c) for c in ['#24252c', '#3e404a', '#62656f', '#8d909a']],
         'rune': [hexc(c) for c in ['#141826', '#1c2236', '#252c44', '#30395a']],
         'runeon': [hexc(c) for c in ['#3aa8ff', '#5fd0ff', '#9cecff', '#e4fbff']],
         'gold': [hexc(c) for c in ['#5e3f0e', '#a87822', '#ecc355', '#fff1a6']],
         'sandstone': [hexc(c) for c in ['#4f4436', '#776a52', '#a39476', '#cfc29e']]}

def vnoise3(q, f, seed=0):
    return (np.sin(q[:, 0] * f + seed) * np.sin(q[:, 1] * f * 1.3 + seed * 2) * np.sin(q[:, 2] * f * 0.9 + seed * 3))

def rock(seed, r=10, sq=(1.3, 0.8, 1.0), mossy=True):
    def fn(q):
        qq = q / np.array(sq)
        return (np.linalg.norm(qq, axis=1) - r) * min(sq) + 1.4 * vnoise3(q, 0.35, seed) + 0.6 * vnoise3(q, 0.9, seed + 1)
    paint = (lambda q: [('moss' if (y > r * 0.35 * sq[1] and mossy) else None) for x, y, z in q])
    pr = Prim('custom', 'rock', (0, 0, 0), fn=fn, paint=paint)
    w = int(r * sq[0] * 2.6 + 8); h = int(r * sq[1] * 2.4 + 8)
    img, _ = render([pr], STONE, w, h, origin=(0, r * sq[1] * 0.25), yaw=np.radians(seed * 40), pitch=np.radians(18), outline='#16131a')
    # cut the part below ground (bottom rows)
    return img
add('rock0', rock(1)); add('rock1', rock(2, 8, (1.5, 0.7, 1.1))); add('rock2', rock(3, 14, (1.2, 0.9, 1.0)))
add('rock3', rock(4, 6, (1.3, 0.8, 1.0), mossy=False)); add('rockbig', rock(5, 22, (1.4, 0.95, 1.0)))

def crate():
    def paint(q):
        out = []
        for x, y, z in q:
            edge = (abs(abs(x) - 5.2) < 0.9) + (abs(abs(y) - 5.2) < 0.9) + (abs(abs(z) - 5.2) < 0.9)
            out.append('wooddk' if edge >= 2 else ('wooddk' if (abs(y) % 2.6) < 0.35 else None))
        return out
    pr = Prim('rbox', 'wood', (0, 0, 0), b=(6, 6, 6), round=0.4, paint=paint)
    img, _ = render([pr], STONE, 26, 26, origin=(0, 0.5), yaw=np.radians(30), pitch=np.radians(18), outline='#1a120c')
    return img
add('crate', crate())

def barrel():
    def paint(q):
        return [('iron' if abs(abs(y) - 4.5) < 0.8 else ('wooddk' if (math.atan2(z, x) * 5) % 1 < 0.12 else None)) for x, y, z in q]
    def fn(q):
        rr = 5.0 + 0.9 * np.cos(q[:, 1] / 7.0 * np.pi / 2)
        radial = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - rr
        return np.maximum(radial, np.abs(q[:, 1]) - 7)
    pr = Prim('custom', 'wood', (0, 0, 0), fn=fn, paint=paint)
    img, _ = render([pr], STONE, 20, 24, origin=(0, 0.5), yaw=0.3, pitch=np.radians(18), outline='#1a120c')
    return img
add('barrel', barrel())

def pillar(seed, h=26, broken=True):
    def fn(q):
        ang = np.arctan2(q[:, 2], q[:, 0])
        rr = 5 + 0.45 * np.cos(ang * 10)
        d = np.maximum(np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - rr, np.abs(q[:, 1]) - h / 2)
        if broken:
            d = np.maximum(d, (q[:, 1] - h / 2 + 4) + 0.35 * q[:, 0] + 1.2 * np.sin(q[:, 2] * 1.3 + q[:, 0]))
        cap = np.maximum(np.maximum(np.abs(q[:, 0]) - 6.5, np.abs(q[:, 2]) - 6.5), np.abs(q[:, 1] + h / 2 - 1.2) - 1.5)
        return np.minimum(d, cap)
    pr = Prim('custom', 'stone', (0, 0, 0), fn=fn,
              paint=lambda q: [('moss' if (math.sin(x * 0.9 + y * 0.5) + math.sin(z * 0.7 - y * 0.8) > 0.9) else None) for x, y, z in q])
    img, _ = render([pr], STONE, 20, h + 8, origin=(0, 0.5), yaw=0.4 + seed, pitch=np.radians(14), outline='#141320')
    return img
add('pillar0', pillar(0)); add('pillar1', pillar(1.3, 34))

RUNE_GLYPH = ["..#..", ".#.#.", "#.#.#", ".###.", "..#..", ".#.#.", "#...#"]
def runestone(lit):
    def paint(q):
        out = []
        for x, y, z in q:
            m = None
            if z > 2.0:
                gx = int(math.floor((x + 2.5))); gy = int(math.floor((6 - y) / 1.4))
                if 0 <= gx < 5 and 0 <= gy < 7 and RUNE_GLYPH[gy][gx] == '#':
                    m = 'runeon' if lit else 'rune'
            if m is None and y < -6 and (math.sin(x * 2) > 0.2):
                m = 'moss'
            out.append(m)
        return out
    pr = Prim('rbox', 'stone', (0, 0, 0), R=rot_z(0.06), b=(4.8, 10, 2.6), round=1.6, paint=paint)
    img, _ = render([pr], STONE, 20, 30, origin=(0, 0), yaw=np.radians(-12), pitch=np.radians(10), outline='#141320')
    return img
a, b = runestone(False), runestone(True)
add('runestone', a)
glow = np.zeros_like(b); diff = np.any(a != b, axis=2); glow[diff] = b[diff]
add('runestone_glow', glow)

def signpost():
    img = blank(34, 40)
    for y in range(8, 40):
        for x in (15, 16, 17):
            put(img, x, y, H(['#8a5e34', '#6a4528', '#4a2e1a'][x - 15]))
    # arrow board pointing right (east)
    for y in range(8, 17):
        for x in range(4, 30):
            tip = 30 - abs(y - 12.5) * 1.1
            if x < tip:
                c = '#b4844a' if y < 10 else '#8a5e34' if y < 15 else '#6a4528'
                if (x * 7 + y * 3) % 11 == 0: c = '#5e3c20'
                put(img, x, y, H(c))
    for x in range(8, 24, 4):
        put(img, x, 12, H('#3a2414'))  # weathered carved marks
    return outline(img, '#1a120c')
add('signpost', signpost())

def driftwood():
    img = blank(44, 10)
    for x in range(2, 42):
        th = 3 if 6 < x < 36 else 2
        for y in range(5 - th // 2, 5 + th // 2 + 1):
            put(img, x, y + (1 if x > 30 else 0), H(['#c8b08a', '#a08a68', '#7a6a50'][min(2, y - (5 - th // 2))]))
    return outline(img, '#3a3024')
add('driftwood', driftwood())

def shells():
    img = blank(8, 5)
    for x, y, c in ((1, 3, '#f4d6c8'), (2, 3, '#e8a890'), (2, 2, '#f4d6c8'), (5, 3, '#fff2e0'), (6, 3, '#e8d0b0')):
        put(img, x, y, H(c))
    return img
add('shells', shells())

# ------------------------------------------------------------------ boat (side profile, faces right)
def boat():
    w, h = 96, 78
    back = blank(w, h); front = blank(w, h)
    def hull_y(x):  # top edge of hull at x (0..w), gunwale curve
        t = (x - 8) / 80
        return 54 - 6 * (t - 0.5) ** 2 * 4 * 0.5 - (6 if t > 0.92 else 0) * 0
    for x in range(6, 92):
        t = (x - 6) / 86
        top = int(round(52 - 7 * (abs(t - 0.45) ** 2) * 4 - (t > 0.85) * (t - 0.85) * 30))
        bottom = int(round(66 - 8 * (abs(t - 0.45) * 2) ** 3))
        if bottom <= top: continue
        for y in range(top, bottom + 1):
            k = (y - top) / max(1, bottom - top)
            plank = int(k * 4)
            base = ['#b4844a', '#9a6a3a', '#80562e', '#64401f', '#4a2e16'][min(4, plank)]
            if abs(k * 4 - round(k * 4)) < 0.12 and 0 < k < 1: base = '#3a2414'
            put(front, x, y, H(base))
        put(front, x, top, H('#d4a464')); put(front, x, top + 1, H('#3a2414'))
    # interior (back layer): dark planks visible above far gunwale
    for x in range(10, 88):
        t = (x - 6) / 86
        top = int(round(52 - 7 * (abs(t - 0.45) ** 2) * 4 - (t > 0.85) * (t - 0.85) * 30))
        for y in range(top - 3, top + 1):
            put(back, x, y, H('#5e3c20' if y > top - 2 else '#8a5e34'))
    # mast + furled sail + small flag
    for y in range(8, 52):
        put(back, 40, y, H('#6a4528')); put(back, 41, y, H('#4a2e1a'))
    for y in range(14, 48):
        span = int((y - 14) * 0.62)
        for x in range(42, 42 + span):
            c = '#f4ead2' if x < 42 + span - 3 else '#d8c8a4'
            if (y + x) % 9 == 0: c = '#e2d4b4'
            put(back, x, y, H(c))
    for y in range(9, 14):
        for x in range(42, 42 + (14 - y) * 2):
            put(back, x, y, H('#2cbdb7' if y < 12 else '#147f8a'))
    # yard
    for x in range(41, 64): put(back, x, 47, H('#6a4528'))
    back = outline(back, '#1a120c'); front = outline(front, '#1a120c')
    return back, front
bb, bf = boat()
add('boat_back', bb, (48, 66)); add('boat_front', bf, (48, 66))

# ------------------------------------------------------------------ portal (frontal, faces viewer)
DSI = {'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
       'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
       'I': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"]}
def portal_frame(lit):
    Rr, rr = 27.0, 5.6
    nseg = 14
    def ring_fn(q):
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        rad = np.sqrt(x * x + y * y)
        # square-ish cross-section blocks
        d = np.maximum(np.abs(rad - Rr) - rr, np.abs(z) - 4.2) - 0.0
        ang = np.arctan2(y, x)
        seg = np.abs(((ang / (2 * np.pi) * nseg) % 1) - 0.5)
        groove = np.clip(0.06 - (0.5 - seg) * 0.0, 0, 1)
        d = d + np.where(seg > 0.46, 0.5, 0.0)
        return d
    def ring_paint(q):
        out = []
        for x, y, z in q:
            rad = math.hypot(x, y); ang = math.atan2(y, x)
            segf = (ang / (2 * math.pi) * nseg) % 1
            m = None
            if z > 3.6 and abs(rad - Rr) < 2.6 and 0.3 < segf < 0.7:
                # small carved rune dot pattern per block
                si = int((ang / (2 * math.pi) * nseg) % nseg)
                lx = (segf - 0.5) * 2 * math.pi * Rr / nseg; ly = rad - Rr
                pat = [(0, 0), (-1.4, 1.2), (1.4, 1.2), (0, -1.4)] if si % 2 else [(-1, 0), (1, 0), (0, 1.5), (0, -1.5)]
                for (px, py) in pat:
                    if (lx - px) ** 2 + (ly - py) ** 2 < 0.55:
                        m = 'runeon' if lit else 'rune'
            if m is None and (math.sin(ang * 3 + 1) > 0.75 and rad > Rr + 2) and ang < -0.3:
                m = 'moss'
            out.append(m)
        return out
    ring = Prim('custom', 'stone', (0, 34, 0), fn=ring_fn, paint=ring_paint)
    def key_paint(q):
        out = []
        for x, y, z in q:
            m = None
            if z > 4.6:
                # DSI letters, each 5x7 cells of 0.9 units
                cell = 0.92
                gx = (x + 8.3) / cell; gy = (2.9 - y) / cell
                li = int(gx // 6); cx_ = int(gx % 6); cy_ = int(gy)
                if 0 <= li < 3 and 0 <= cx_ < 5 and 0 <= cy_ < 7 and gx >= 0:
                    if DSI['DSI'[li]][cy_][cx_] == '#':
                        m = 'runeon' if lit else 'gold'
            out.append(m)
        return out
    key = Prim('rbox', 'sandstone', (0, 34 + Rr + 1.0, 0.6), b=(9.6, 5.0, 5.2), round=0.9, paint=key_paint)
    plinthL = Prim('rbox', 'stone', (-Rr + 1, 4.5, 0), b=(7.5, 4.5, 6), round=0.8)
    plinthR = Prim('rbox', 'stone', (Rr - 1, 4.5, 0), b=(7.5, 4.5, 6), round=0.8)
    step = Prim('rbox', 'stone', (0, 1.4, 1.5), b=(36, 1.4, 8), round=0.5,
                paint=lambda q: [('moss' if math.sin(x * 0.7) > 0.6 and z > 5 else None) for x, y, z in q])
    step2 = Prim('rbox', 'sandstone', (0, 3.6, 0), b=(22, 1.2, 6), round=0.4)
    prims = [ring, key, plinthL, plinthR, step, step2]
    img, _ = render(prims, STONE, 96, 104, origin=(0, 34), scale=1.0, yaw=0.0, pitch=np.radians(6), outline='#11121c',
                    lights={'key': (-0.45, 0.7, 0.6)})
    return img
pa, pb = portal_frame(False), portal_frame(True)
# vines on the portal (2D overlay)
def vines(img, seed):
    r_ = np.random.default_rng(seed); img = img.copy(); h, w = img.shape[:2]
    for i in range(5):
        x = int(r_.uniform(10, w - 10)); y = int(r_.uniform(10, 50))
        for s in range(int(r_.uniform(10, 26))):
            yy = y + s; xx = x + int(2 * math.sin(s * 0.4 + i))
            if 0 <= yy < h and img[yy, xx, 3] > 0:
                put(img, xx, yy, H('#2e6a34' if s % 3 else '#5aa046'))
                if s % 4 == 0: put(img, xx + 1, yy, H('#78b850'))
    return img
pa = vines(pa, 3); pb = vines(pb, 3)
add('portal', pa, (48, 103))
g = np.zeros_like(pb); diff = np.any(pa != pb, axis=2); g[diff] = pb[diff]
add('portal_runes', g, (48, 103))

def portal_energy(frame, n=12):
    R0 = 21
    size = R0 * 2 + 2
    img = blank(size, size)
    ramp = ['#0b1f5c', '#14389a', '#1f63d6', '#3a9cf2', '#6fd2ff', '#b6f2ff', '#ffffff']
    ph = frame / n * 2 * math.pi
    for y in range(size):
        for x in range(size):
            dx = x + 0.5 - size / 2; dy = y + 0.5 - size / 2
            r = math.hypot(dx, dy) / R0
            if r > 1: continue
            a = math.atan2(dy, dx)
            v = 0.5 + 0.5 * math.sin(a * 3 + r * 9 - ph * 1) * 0.6 + 0.25 * math.sin(a * 5 - r * 14 + ph * 2)
            v = v * 0.55 + (1 - r) * 0.75
            v += (BAYER[y % 4, x % 4] - 0.5) * 0.25
            if r > 0.9: v = max(v, 0.85)  # bright inner rim
            idx = int(np.clip(v * len(ramp) * 0.9, 0, len(ramp) - 1))
            put(img, x, y, H(ramp[idx]))
    return img
for f in range(12):
    add(f'portal_energy_{f}', portal_energy(f), (22, 22))

def glow_sprite(R=48, col='#5fd0ff', levels=6):
    size = R * 2
    img = blank(size, size)
    c = H(col)
    for y in range(size):
        for x in range(size):
            r = math.hypot(x + 0.5 - R, y + 0.5 - R) / R
            if r >= 1: continue
            v = (1 - r) ** 1.6 + (BAYER[y % 4, x % 4] - 0.5) * 0.12
            lv = int(np.clip(v * levels, 0, levels))
            if lv <= 0: continue
            img[y, x, :3] = c; img[y, x, 3] = int(255 * lv / levels)
    return img
add('glow_blue', glow_sprite(48, '#4fc4ff'), (48, 48))
add('glow_warm', glow_sprite(40, '#ffd27a'), (40, 40))

# ------------------------------------------------------------------ backdrop: mountain, islands, clouds, sun
def mountain(w=440, h=260, seed=5, ramp_rock=None, haze=0.0, peak=0.5):
    r_ = np.random.default_rng(seed)
    xs = np.arange(w)
    t = xs / w
    base = 1 - np.abs(t - peak) * 2.0
    base = np.clip(base, 0, 1) ** 1.25
    prof = base * 0.92 + 0.04 * np.sin(t * 23 + seed) + 0.03 * np.sin(t * 57 + seed * 2) + 0.02 * np.sin(t * 131)
    prof[np.abs(t - peak) < 0.04] *= 0.97  # crater notch
    top = (h - prof * (h - 6)).astype(int)
    img = blank(w, h)
    forest = ['#123a2a', '#1a5034', '#26683e', '#3a8448', '#5aa252']
    rock = ['#3a3f4a', '#555b66', '#767c86', '#9aa0a8']
    for x in range(w):
        for y in range(max(0, top[x]), h):
            elev = 1 - (y - top.min()) / (h - top.min())
            side = (x - w * peak) / (w * 0.5)
            ang = math.atan2(x - w * peak, (y - top.min()) + 8)
            ridge = math.sin(ang * 16 + math.sin(y * 0.05) * 0.8)
            lit = -side * 0.45 + ridge * 0.22 + math.sin(x * 0.31 + y * 0.17) * 0.08
            lit += (BAYER[y % 4, x % 4] - 0.5) * 0.3 - (y - top[x]) / h * 0.4
            if elev > 0.72 - 0.08 * math.sin(x * 0.07):
                cols = rock
            else:
                cols = forest
            idx = int(np.clip((lit + 0.6) * len(cols) / 1.4, 0, len(cols) - 1))
            put(img, x, y, H(cols[idx]))
    # mist band
    for y in range(int(h * 0.55), int(h * 0.68)):
        for x in range(w):
            if img[y, x, 3] and BAYER[y % 4, x % 4] < 0.5 - abs(y - h * 0.615) / (h * 0.065) * 0.5:
                img[y, x, :3] = (img[y, x, :3] * 0.35 + np.array(H('#cfe8ee')) * 0.65).astype(np.uint8)
    if haze > 0:
        img[..., :3] = (img[..., :3] * (1 - haze) + np.array(H('#9fd0e4')) * haze).astype(np.uint8)
    return img
add('mountain', mountain(), (220, 259))

def island_sil(w, h, seed, col_top, col_bot):
    r_ = np.random.default_rng(seed)
    img = blank(w, h); t = np.arange(w) / w
    prof = np.clip(1 - np.abs(t - 0.5 + r_.uniform(-0.1, 0.1)) * 2.2, 0, 1) ** 0.8 * (h - 2)
    prof += np.sin(t * 17 + seed) * 2 + np.sin(t * 41) * 1
    for x in range(w):
        for y in range(int(h - prof[x]), h):
            k = (y - (h - prof[x])) / max(1, prof[x])
            c = col_top if (k < 0.4 or BAYER[y % 4, x % 4] > k) else col_bot
            put(img, x, y, H(c))
    return img
add('isle_far0', island_sil(180, 26, 1, '#7fb3c8', '#6aa2ba'))
add('isle_far1', island_sil(120, 18, 2, '#8cc0d2', '#78b0c6'))
add('isle_mid0', island_sil(150, 34, 3, '#4f8f8a', '#3f7a7c'))

def cloud(seed, w, h, n):
    r_ = np.random.default_rng(seed)
    blobs = [(w / 2 + r_.uniform(-w * 0.32, w * 0.32), h * 0.62 - r_.uniform(0, h * 0.28), r_.uniform(h * 0.22, h * 0.42)) for _ in range(n)]
    img = shade_blobs(w, h, blobs, ['#9cc4dc', '#c6e0ee', '#eef8ff', '#ffffff'], light=(-0.5, -0.9), noise=0.05, seed=seed, texture=False)
    img[int(h * 0.74):, :, :] = 0  # flat bottom
    return img
add('cloud0', cloud(1, 120, 50, 9)); add('cloud1', cloud(2, 80, 36, 7)); add('cloud2', cloud(3, 160, 60, 12)); add('cloud3', cloud(4, 60, 26, 5))

def sun():
    s = 72; img = blank(s, s)
    for y in range(s):
        for x in range(s):
            r = math.hypot(x + 0.5 - s / 2, y + 0.5 - s / 2)
            if r < 9: put(img, x, y, H('#fffbe8'))
            elif r < 11: put(img, x, y, H('#fff1b8'))
            elif r < 36:
                v = (1 - (r - 11) / 25) ** 2 + (BAYER[y % 4, x % 4] - 0.5) * 0.2
                lv = int(np.clip(v * 4, 0, 4))
                if lv > 0:
                    img[y, x, :3] = H('#ffe9a8'); img[y, x, 3] = 40 * lv
    return img
add('sun', sun(), (36, 36))

# ------------------------------------------------------------------ DSI logo
def dsi_logo(cell=6):
    gap = 1
    lw = 5 * cell; lh = 7 * cell
    w = lw * 3 + cell * 2 * gap + 16; h = lh + 16
    img = blank(w, h)
    m = np.zeros((h, w), bool)
    for li, ch in enumerate('DSI'):
        ox = 8 + li * (lw + cell * gap); oy = 8
        for gy in range(7):
            for gx in range(5):
                if DSI[ch][gy][gx] == '#':
                    m[oy + gy * cell: oy + (gy + 1) * cell, ox + gx * cell: ox + (gx + 1) * cell] = True
    # bevel: compare with shifted masks
    up = np.roll(m, 1, 0); lf = np.roll(m, 1, 1); dn = np.roll(m, -1, 0); rt = np.roll(m, -1, 1)
    yy, xx = np.mgrid[0:h, 0:w]
    grad = (yy - 8) / lh
    base_cols = np.array([H(c) for c in ['#fff1a6', '#f6d36a', '#ecc355', '#d9a53a', '#b8862a']])
    gi = np.clip((grad * 5 + (BAYER[yy % 4, xx % 4] - 0.5)).astype(int), 0, 4)
    img[m, :3] = base_cols[gi][m]; img[m, 3] = 255
    hl = m & (~up | ~lf); img[hl, :3] = H('#fffbe0')
    sh = m & (~dn | ~rt) & ~hl; img[sh, :3] = H('#7a5212')
    # inner blue line (portal light reflection) under the highlight
    img = outline(img, '#2a1a06')
    img = outline(img, '#0c1a3a')
    return img
add('dsi_logo', dsi_logo(6), None)
add('dsi_logo_small', dsi_logo(3), None)

# ------------------------------------------------------------------ pack atlas
def pack(assets, maxw=1024):
    items = sorted(assets.items(), key=lambda kv: -kv[1][0].shape[0])
    x = y = rowh = 0; places = {}
    for name, (img, anc) in items:
        h, w = img.shape[:2]
        if x + w > maxw:
            x = 0; y += rowh + 1; rowh = 0
        places[name] = (x, y, w, h, anc); x += w + 1; rowh = max(rowh, h)
    H_ = y + rowh
    atlas = np.zeros((H_, maxw, 4), np.uint8)
    for name, (x, y, w, h, anc) in places.items():
        atlas[y:y + h, x:x + w] = assets[name][0]
    meta = {n: {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h), 'ax': int(a[0]), 'ay': int(a[1])} for n, (x, y, w, h, a) in places.items()}
    return atlas, meta

out = sys.argv[1]
atlas, meta = pack(ASSETS)
Image.fromarray(atlas).save(os.path.join(out, 'environment_atlas.png'))
json.dump(meta, open(os.path.join(out, 'environment_atlas.json'), 'w'), indent=0)
print('atlas', atlas.shape, len(meta))
