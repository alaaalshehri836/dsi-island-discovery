"""Tiny vectorised SDF toolkit + toon pixel-art renderer (numpy).

Models are lists of primitives. Each primitive has a local frame (center + 3x3
rotation), a material name and an optional paint(p_local)->material override.
render() ray-marches an orthographic view at an exact pixel grid (1 ray per pixel,
no anti-aliasing) and returns crisp RGBA pixel art with toon ramps + outlines.
"""
import numpy as np

def rot_x(a):
    c, s = np.cos(a), np.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def rot_y(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rot_z(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

def hexc(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)

class Prim:
    def __init__(self, kind, mat, center=(0, 0, 0), R=None, paint=None, **kw):
        self.kind, self.mat, self.paint = kind, mat, paint
        self.c = np.asarray(center, dtype=np.float64)
        self.R = np.eye(3) if R is None else np.asarray(R, dtype=np.float64)
        self.kw = kw
        self.clip = kw.pop('clip', None)  # optional fn(p_local)->sdf to intersect with

    def local(self, P):
        return (P - self.c) @ self.R  # R columns are local axes in world

    def sdf_local(self, q):
        k, kw = self.kind, self.kw
        if k == 'sphere':
            d = np.linalg.norm(q, axis=1) - kw['r']
        elif k == 'ellipsoid':
            r = np.asarray(kw['r'], dtype=np.float64)
            k0 = np.linalg.norm(q / r, axis=1); k1 = np.linalg.norm(q / (r * r), axis=1)
            d = k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        elif k == 'rbox':
            b = np.asarray(kw['b'], dtype=np.float64); rr = kw.get('round', 0.0)
            qq = np.abs(q) - (b - rr)
            d = np.linalg.norm(np.maximum(qq, 0), axis=1) + np.minimum(np.max(qq, axis=1), 0) - rr
        elif k == 'capsule':  # local: segment from a to b (given in local coords), radii ra->rb
            a = np.asarray(kw['a'], dtype=np.float64); b = np.asarray(kw['b'], dtype=np.float64)
            ra, rb = kw['ra'], kw.get('rb', kw['ra'])
            pa = q - a; ba = b - a
            h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
            d = np.linalg.norm(pa - h[:, None] * ba, axis=1) - (ra + (rb - ra) * h)
        elif k == 'cyl':  # along local y, radius r (or rx/rz ellipse), half height h, rounding
            rx = kw.get('rx', kw.get('r')); rz = kw.get('rz', kw.get('r')); h = kw['h']; rr = kw.get('round', 0.0)
            radial = np.sqrt((q[:, 0] / rx) ** 2 + (q[:, 2] / rz) ** 2) * min(rx, rz) - (min(rx, rz) - rr)
            dy = np.abs(q[:, 1]) - (h - rr)
            d = np.minimum(np.maximum(radial, dy), 0) + np.linalg.norm(np.stack([np.maximum(radial, 0), np.maximum(dy, 0)], 1), axis=1) - rr
        elif k == 'torus':  # in local xz plane
            Rr, r = kw['Rmaj'], kw['r']
            qx = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - Rr
            d = np.sqrt(qx ** 2 + q[:, 1] ** 2) - r
        elif k == 'custom':
            d = kw['fn'](q)
        else:
            raise ValueError(k)
        if self.clip is not None:
            d = np.maximum(d, self.clip(q))
        return d

    def sdf(self, P):
        return self.sdf_local(self.local(P))

def scene_sdf(prims, P):
    d = np.full(len(P), 1e9)
    for pr in prims:
        d = np.minimum(d, pr.sdf(P))
    return d

def camera_basis(yaw, pitch):
    # camera orbits around +Y. yaw=0 -> camera on +Z looking at -Z (front view)
    pos = np.array([np.sin(yaw) * np.cos(pitch), np.sin(pitch), np.cos(yaw) * np.cos(pitch)])
    d = -pos
    right = np.array([np.cos(yaw), 0.0, -np.sin(yaw)])
    up = np.cross(right, d)
    return d, right, up

def render(prims, ramps, W, H, origin, scale=1.0, yaw=0.0, pitch=np.radians(10), lights=None,
           outline='#1d1220', inner_lines=True, steps=90, tone_cuts=(-0.35, 0.18, 0.72), ambient_occl=True,
           outline_mode='hard'):
    """origin: world point that maps to the pixel (W/2, H*?) -> we use origin=(ox,oy) world coordinates
    of the image center along right/up axes. scale: pixels per world unit."""
    d, right, up = camera_basis(yaw, pitch)
    jj, ii = np.meshgrid(np.arange(W), np.arange(H))
    u = (jj + 0.5 - W / 2) / scale + origin[0]
    v = -(ii + 0.5 - H / 2) / scale + origin[1]
    O = (u.reshape(-1, 1) * right + v.reshape(-1, 1) * up) - d * 80.0
    N = len(O)
    t = np.zeros(N); hit = np.zeros(N, bool); alive = np.ones(N, bool)
    for _ in range(steps):
        idx = np.where(alive)[0]
        if len(idx) == 0:
            break
        P = O[idx] + t[idx, None] * d
        dist = scene_sdf(prims, P)
        h = dist < 0.01
        hit[idx[h]] = True; alive[idx[h]] = False
        t[idx[~h]] += np.maximum(dist[~h] * 0.9, 0.02)
        far = t > 200
        alive &= ~far
    img = np.zeros((N, 4))
    hidx = np.where(hit)[0]
    P = O[hidx] + t[hidx, None] * d
    # material: argmin primitive
    D = np.stack([pr.sdf(P) for pr in prims], 1)
    which = np.argmin(D, 1)
    mats = np.empty(len(hidx), dtype=object)
    for k, pr in enumerate(prims):
        sel = which == k
        if not np.any(sel):
            continue
        if pr.paint is not None:
            m = pr.paint(pr.local(P[sel]))
            mats[sel] = [mm if mm is not None else pr.mat for mm in m]
        else:
            mats[sel] = pr.mat
    # normals
    e = 0.04
    nrm = np.stack([scene_sdf(prims, P + e * ax) - scene_sdf(prims, P - e * ax) for ax in np.eye(3)], 1)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    # ambient occlusion (cheap, 3 taps along normal)
    ao = np.ones(len(hidx))
    if ambient_occl:
        acc = 0
        for k, dd in enumerate((0.6, 1.3, 2.4)):
            acc += np.maximum(0, dd - scene_sdf(prims, P + nrm * dd)) / dd * (0.5 ** k)
        ao = np.clip(1 - acc * 0.9, 0, 1)
    if lights is None:
        lights = default_lights()
    # key light in view space -> world
    key = lights['key']
    Lw = key[0] * right + key[1] * up + key[2] * (-d)
    Lw /= np.linalg.norm(Lw)
    ndl = nrm @ Lw
    ndl = ndl - (1 - ao) * 0.9
    tone = np.digitize(ndl, tone_cuts)  # 0..3
    rgb = np.zeros((len(hidx), 3))
    for i in range(len(hidx)):
        rgb[i] = ramps[mats[i]][tone[i]]
    # coloured extra lights (rim / portal glow) in view space
    for (ldir, col, strength, cut) in lights.get('extra', []):  # view space
        Lx = ldir[0] * right + ldir[1] * up + ldir[2] * (-d); Lx = Lx / np.linalg.norm(Lx)
        a = nrm @ Lx
        lvl = np.where(a > cut + 0.35, 1.0, np.where(a > cut, 0.55, 0.0)) * strength
        rgb = rgb * (1 - lvl[:, None] * 0.32) + hexc(col) * lvl[:, None] * 0.32
    for (Lw2, col, strength, cut) in lights.get('extra_world', []):
        Lx = np.asarray(Lw2, dtype=np.float64); Lx = Lx / np.linalg.norm(Lx)
        a = nrm @ Lx
        lvl = np.where(a > cut + 0.4, 1.0, np.where(a > cut, 0.5, 0.0)) * strength
        c = hexc(col)
        rgb = rgb * (1 - lvl[:, None] * 0.3) + c * lvl[:, None] * 0.3
    tint = lights.get('tint')
    if tint is not None:
        rgb = rgb * (1 - tint[1]) + rgb * hexc(tint[0]) / 255 * tint[1]
    img[hidx, :3] = np.clip(rgb, 0, 255); img[hidx, 3] = 255
    img = img.reshape(H, W, 4)
    depth = np.full(N, np.inf); depth[hidx] = t[hidx]; depth = depth.reshape(H, W)
    mask = hit.reshape(H, W)
    matgrid = np.full(N, None, dtype=object); matgrid[hidx] = mats; matgrid = matgrid.reshape(H, W)
    # inner lines at depth discontinuities: darken the farther pixel
    if inner_lines:
        out = img.copy()
        for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nb = np.roll(np.roll(depth, -dy, 0), -dx, 1)
            nbm = np.roll(np.roll(mask, -dy, 0), -dx, 1)
            far = mask & nbm & (depth - nb > 1.8)
            ys, xs = np.where(far)
            for y, x in zip(ys, xs):
                out[y, x, :3] = ramps[matgrid[y, x]][0] * 0.85
        img = out
    # exterior outline
    if outline is not None:
        oc = hexc(outline)
        pad = np.pad(mask, 1)
        nb = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
        ol = nb & ~mask
        img[ol, :3] = oc; img[ol, 3] = 255
    return img.astype(np.uint8), mask

def default_lights():
    # key from upper-left-front (view space: x right, y up, z toward camera)
    return {'key': (-0.55, 0.72, 0.5), 'extra': []}
