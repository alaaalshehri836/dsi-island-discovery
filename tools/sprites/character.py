"""The DSI explorer - ONE model, every view and pose is rendered from it.

Coordinate system: units = sprite pixels at 1x. +Y up, the character faces +Z,
+X is the character's LEFT (screen right in the front view). Feet on y=0.
"""
import numpy as np
from sdf import Prim, rot_x, rot_y, rot_z, hexc

R = np.radians

RAMPS_HEX = {
    'skin':   ['#7c3f2b', '#c27652', '#eeb38a', '#ffd9b5'],
    'hair':   ['#3a1e12', '#5c3220', '#7f4a2b', '#a0663a'],
    'hat':    ['#5f3f1d', '#9c6d33', '#d4a65d', '#f2d48f'],
    'band':   ['#1f110c', '#331c13', '#4f2b1c', '#6c3d27'],
    'scarf':  ['#0b4552', '#147f8a', '#2cbdb7', '#86eedb'],
    'shirt':  ['#6f6450', '#ad9f80', '#e8dcc0', '#fff8ea'],
    'vest':   ['#26301a', '#46552a', '#677a39', '#8ea24f'],
    'pants':  ['#33241a', '#57402c', '#7e6146', '#a3835f'],
    'boots':  ['#1a0f09', '#341f13', '#563620', '#7a5233'],
    'leather':['#341a0d', '#653719', '#985a2a', '#c47e3d'],
    'gold':   ['#5e3f0e', '#a87822', '#ecc355', '#fff1a6'],
    'canvas': ['#33321e', '#58542f', '#7f7946', '#a59f64'],
    'roll':   ['#43160f', '#78291d', '#ad4a35', '#d47657'],
    'eye':    ['#140b12', '#140b12', '#1d1219', '#2a1b24'],
    'white':  ['#b9b0a8', '#ddd5cc', '#f6f1ea', '#ffffff'],
    'iris':   ['#1c0f0a', '#2f1a10', '#4a2c18', '#6b4527'],
    'mouth':  ['#5c2a1e', '#7a3a28', '#9c4e37', '#b8664a'],
    'blush':  ['#a8583e', '#d4825e', '#f0a07e', '#ffbe9c'],
}
RAMPS = {k: [hexc(c) for c in v] for k, v in RAMPS_HEX.items()}

DEFAULT_POSE = dict(
    hipL=0, hipR=0, kneeL=0, kneeR=0, footL=0, footR=0,
    shL=4, shR=4, elL=10, elR=10, abL=8, abR=8,  # shoulder swing fwd, elbow bend, abduction (deg)
    lean=0, twist=0, headYaw=0, headPitch=0, headRoll=0, bob=0, crouch=0,
    eyeX=0.0, eyeY=0.0, eyeOpen=1.0, brow=0.0, mouth='closed', detail=1,
    handBrow=None,  # 'R' raises right hand to the brow (shading eyes)
)

def _leg(hip, a_hip, a_knee, a_foot, side, P, detail):
    """hip: world point. angles deg: hip swing (+fwd), knee bend (+), foot pitch."""
    L1, L2 = 8.9, 8.4
    th = R(a_hip); k = R(a_knee)
    d1 = np.array([0, -np.cos(th), np.sin(th)])
    knee = hip + L1 * d1
    d2 = np.array([0, -np.cos(th - k), np.sin(th - k)])
    ankle = knee + L2 * d2
    fa = R(a_foot)
    toe = ankle + np.array([0, -0.45 - 1.6 * np.sin(fa), 2.5 * np.cos(fa)])
    heel = ankle + np.array([0, -0.6, -0.9])
    out = []
    out.append(Prim('capsule', 'pants', (0, 0, 0), a=hip, b=knee, ra=1.95, rb=1.62))
    boot_top = knee + 0.42 * (ankle - knee)
    out.append(Prim('capsule', 'pants', (0, 0, 0), a=knee, b=boot_top, ra=1.62, rb=1.55))
    out.append(Prim('capsule', 'boots', (0, 0, 0), a=boot_top, b=ankle, ra=1.62, rb=1.42,
                    paint=lambda q, bt=boot_top: [('leather' if abs(y - bt[1]) < 0.55 else None) for y in q[:, 1]] if False else [None] * len(q)))
    out.append(Prim('capsule', 'boots', (0, 0, 0), a=heel, b=toe, ra=1.35, rb=1.2))
    return out, knee, ankle

def _arm(sh, a_sw, a_el, a_ab, sgn, P):
    L1, L2 = 6.0, 5.4
    s, e, ab = R(a_sw), R(a_el), R(a_ab)
    d1 = np.array([sgn * np.sin(ab), -np.cos(ab) * np.cos(s), np.cos(ab) * np.sin(s)])
    el = sh + L1 * d1
    d2 = np.array([sgn * np.sin(ab) * 0.6, -np.cos(ab) * np.cos(s + e), np.cos(ab) * np.sin(s + e)])
    d2 /= np.linalg.norm(d2)
    wr = el + L2 * d2
    return el, wr, d2

def build(pose=None):
    p = dict(DEFAULT_POSE); p.update(pose or {})
    det = p['detail']
    prims = []
    crouch = p['crouch']
    pelvis = np.array([0, 19.7 - crouch + p['bob'], 0])
    # legs ----------------------------------------------------------
    for side, sgn in (('L', 1), ('R', -1)):
        hip = pelvis + np.array([sgn * 2.25, -0.6, 0])
        out, knee, ankle = _leg(hip, p['hip' + side], p['knee' + side], p['foot' + side], side, p, det)
        prims += out
    # pelvis / shorts
    prims.append(Prim('ellipsoid', 'pants', pelvis + np.array([0, 0.3, 0]), r=(4.15, 2.9, 2.75)))
    # upper body frame (lean + twist about pelvis)
    UB = rot_y(R(p['twist'])) @ rot_x(R(p['lean']))
    def U(v):
        return pelvis + UB @ np.asarray(v, dtype=np.float64)
    # abdomen + belt
    def belly_paint(q):
        out = []
        for x, y, z in q:
            if -1.95 < y < -0.7:
                out.append('gold' if (z > 1.5 and abs(x) < 0.75) else 'leather')
            elif z > 0 and abs(x) < 1.25 and y > -0.7:
                out.append('shirt')
            else:
                out.append('vest' if y > -0.7 else 'pants')
        return out
    prims.append(Prim('ellipsoid', 'vest', U((0, 4.1, 0)), R=UB, r=(3.95, 3.7, 2.6), paint=belly_paint))
    # chest
    def chest_paint(q):
        out = []
        for x, y, z in q:
            m = None
            if z > 0.4 and abs(x) < 1.35 - 0.12 * y:  # open vest -> shirt between panels (V neck)
                m = 'shirt'
            elif y > 2.6 and abs(x) > 3.3:
                m = 'shirt'  # shoulders
            else:
                m = 'vest'
            # backpack shoulder straps (front)
            if z > 0.8 and 1.75 < abs(x) < 2.65 and y > -2.5:
                m = 'leather'
            out.append(m)
        return out
    prims.append(Prim('ellipsoid', 'vest', U((0, 8.4, 0.05)), R=UB, r=(4.85, 4.2, 2.85), paint=chest_paint))
    # belt pouch (character's right hip)
    prims.append(Prim('rbox', 'leather', U((-3.9, 1.6, 1.0)), R=UB, b=(0.9, 1.5, 1.4), round=0.5,
                      paint=lambda q: [('gold' if (y > 0.4 and abs(z) < 0.35) else None) for x, y, z in q]))
    # backpack + bedroll
    def pack_paint(q):
        return [('leather' if (abs(x) < 2.6 and -0.4 < y < 0.4) or (abs(x) > 2.6 and False) else ('leather' if abs(y + 1.6) < 0.25 and z < -0.5 else None)) for x, y, z in q]
    prims.append(Prim('rbox', 'canvas', U((0, 7.4, -3.85)), R=UB, b=(3.25, 3.9, 1.45), round=1.1, paint=pack_paint))
    prims.append(Prim('rbox', 'canvas', U((0, 5.0, -5.15)), R=UB, b=(2.2, 1.3, 0.55), round=0.45,
                      paint=lambda q: [('leather' if y > 0.7 else None) for x, y, z in q]))
    prims.append(Prim('cyl', 'roll', U((0, 12.0, -3.5)), R=UB @ rot_z(R(90)), r=1.55, h=3.9, round=0.6,
                      paint=lambda q: [('leather' if (abs(abs(y) - 2.2) < 0.38) else None) for x, y, z in q]))
    # neck + scarf
    prims.append(Prim('capsule', 'skin', (0, 0, 0), a=U((0, 11.2, 0)), b=U((0, 14.0, 0.25)), ra=1.6))
    prims.append(Prim('torus', 'scarf', U((0, 12.15, 0.25)), R=UB @ rot_x(R(-10)), Rmaj=2.15, r=1.18))
    prims.append(Prim('capsule', 'scarf', (0, 0, 0), a=U((1.25, 11.6, 2.15)), b=U((2.0, 9.0, 2.75)), ra=0.95, rb=0.75))
    prims.append(Prim('sphere', 'scarf', U((1.15, 11.75, 2.35)), r=1.0))
    # arms ------------------------------------------------------------
    for side, sgn in (('L', 1), ('R', -1)):
        sh = U((sgn * 4.55, 10.0, 0.0))
        a_sw, a_el, a_ab = p['sh' + side], p['el' + side], p['ab' + side]
        if p['handBrow'] == side:
            a_sw, a_el, a_ab = 95, 70, 6
        el, wr, d2 = _arm(sh, a_sw + 0, a_el, a_ab, sgn, p)
        el = pelvis + UB @ (el - pelvis) if False else el
        cuff = sh + 0.78 * (el - sh)
        prims.append(Prim('capsule', 'shirt', (0, 0, 0), a=sh, b=el, ra=1.42, rb=1.3,
                          paint=None))
        prims.append(Prim('capsule', 'skin', (0, 0, 0), a=el, b=wr, ra=1.18, rb=1.05))
        prims.append(Prim('sphere', 'skin', wr + d2 * 0.75, r=1.28))
    # head ------------------------------------------------------------
    neck_top = U((0, 14.2, 0.3))
    HR = UB @ rot_y(R(p['headYaw'])) @ rot_x(R(-p['headPitch'])) @ rot_z(R(p['headRoll']))
    hc = neck_top + HR @ np.array([0, 3.55, 0.15])
    def H(v):
        return hc + HR @ np.asarray(v, dtype=np.float64)
    ex, ey, eo, brow = p['eyeX'], p['eyeY'], p['eyeOpen'], p['brow']
    mouth = p['mouth']
    def head_paint(q):
        out = []
        for x, y, z in q:
            m = None
            if z > 1.0:
                for sx in (1.55, -1.55):
                    dx = x - sx
                    if det >= 2:
                        # detailed portrait eyes
                        ry = 0.78 * eo
                        if (dx / 0.92) ** 2 + ((y - 0.15) / max(ry, 0.05)) ** 2 < 1 and eo > 0.08:
                            m = 'white'
                            if ((dx - ex * 0.42) / 0.5) ** 2 + ((y - 0.12 - ey * 0.3) / max(min(0.62, ry), 0.05)) ** 2 < 1:
                                m = 'iris'
                                if (dx - ex * 0.42) ** 2 + (y - 0.12 - ey * 0.3) ** 2 < 0.07:
                                    m = 'eye'
                        if abs(y - (0.15 + ry + 0.08)) < 0.17 and abs(dx) < 0.98 and eo > 0.08:
                            m = 'eye'   # upper lid line
                        if eo <= 0.08 and abs(y - 0.1) < 0.14 and abs(dx) < 0.85:
                            m = 'eye'   # closed lid
                        by = 1.5 + brow * 0.45 - 0.14 * dx * dx
                        if abs(y - by) < 0.2 and abs(dx) < 1.05:
                            m = 'hair'
                    else:
                        if abs(dx) < 0.55 and -0.75 < y - 0.1 < 0.85:
                            m = 'eye'
                if det >= 2:
                    if mouth == 'closed' and abs(y + 2.05) < 0.14 and abs(x) < 0.85 - 0.35 * abs(y + 2.05):
                        m = 'mouth'
                    if mouth == 'open' and ((x / 0.6) ** 2 + ((y + 2.1) / 0.42) ** 2) < 1:
                        m = 'mouth'
                    if mouth == 'smile' and abs(y + 2.0 - 0.18 * x * x) < 0.14 and abs(x) < 0.95:
                        m = 'mouth'
                    if ((abs(x) - 2.35) ** 2 / 0.5 + (y + 0.9) ** 2 / 0.25) < 1 and m is None:
                        m = 'blush'
            out.append(m)
        return out
    prims.append(Prim('ellipsoid', 'skin', hc, R=HR, r=(4.35, 4.75, 4.45), paint=head_paint))
    # jaw/chin to give a less spherical head
    prims.append(Prim('ellipsoid', 'skin', H((0, -2.0, 0.7)), R=HR, r=(3.0, 2.3, 3.0)))
    prims.append(Prim('sphere', 'skin', H((0, -0.55, 4.15)), r=0.78))           # nose
    for sgn in (1, -1):
        prims.append(Prim('ellipsoid', 'skin', H((sgn * 3.95, -0.2, -0.35)), R=HR, r=(0.6, 1.05, 0.8)))  # ears
    # hair: back + sides, clipped away from the face
    prims.append(Prim('ellipsoid', 'hair', H((0, 0.65, -0.55)), R=HR, r=(4.35, 4.55, 4.55),
                      clip=lambda q: (q[:, 2] - (0.2 + 0.9 * np.clip(q[:, 1] - 1.6, 0, 9))) * 1.0))
    prims.append(Prim('ellipsoid', 'hair', H((0, -1.4, -2.6)), R=HR, r=(3.2, 2.6, 2.2)))   # nape
    prims.append(Prim('ellipsoid', 'hair', H((-2.4, 2.4, 2.4)), R=HR @ rot_z(R(-25)), r=(2.0, 1.0, 1.4)))  # fringe tuft
    prims.append(Prim('ellipsoid', 'hair', H((2.0, 2.55, 2.5)), R=HR @ rot_z(R(20)), r=(1.8, 0.9, 1.3)))
    for sgn in (1, -1):
        prims.append(Prim('ellipsoid', 'hair', H((sgn * 3.55, 0.4, 1.0)), R=HR, r=(0.75, 1.9, 1.1)))  # sideburns
    # hat
    BR = HR @ rot_x(R(7))
    prims.append(Prim('ellipsoid', 'hat', H((0, 3.55, 0.25)), R=BR, r=(7.3, 0.62, 7.0),
                      paint=lambda q: [('hat' if True else None) for _ in q]))
    def crown_paint(q):
        return [('band' if y < -0.55 else None) for x, y, z in q]
    prims.append(Prim('cyl', 'hat', H((0, 5.0, -0.05)), R=BR, rx=3.95, rz=3.75, h=1.65, round=0.8, paint=crown_paint))
    prims.append(Prim('ellipsoid', 'hat', H((0, 6.3, -0.05)), R=BR, r=(3.75, 1.35, 3.5)))
    return prims

# -------------------------------------------------------------------- poses
def walk_pose(phase):
    s = np.sin(2 * np.pi * phase); c = np.cos(2 * np.pi * phase)
    hipL = 26 * s; hipR = -26 * s
    # knee bends most during swing (leg moving forward)
    kneeL = 8 + max(0, np.cos(2 * np.pi * phase - 0.6)) * 34
    kneeR = 8 + max(0, np.cos(2 * np.pi * (phase + 0.5) - 0.6)) * 34
    footL = -10 * s; footR = 10 * s
    bob = -0.8 * abs(s) + 0.4
    return dict(hipL=hipL, hipR=hipR, kneeL=kneeL, kneeR=kneeR, footL=footL, footR=footR,
                shL=-24 * s, shR=24 * s, elL=14 + 10 * max(0, -s), elR=14 + 10 * max(0, s),
                abL=7, abR=7, bob=bob, lean=5, headPitch=-3)

def idle_pose(k):
    return dict(bob=-0.35 * k, shL=3 + k, shR=3 + k, elL=12 + 2 * k, elR=12 + 2 * k, abL=9, abR=9)

POSES = {
    'idle': [idle_pose(0), idle_pose(1)],
    'walk': [walk_pose(i / 8) for i in range(8)],
    'look': [dict(headYaw=-40, twist=-6), dict(headYaw=0), dict(headYaw=40, twist=6), dict(headYaw=0)],
    'shade': [dict(handBrow='R', headYaw=25, headPitch=4, twist=8)],
    'react': [dict(lean=-9, headPitch=10, shL=18, shR=18, elL=40, elR=40, abL=18, abR=18, hipL=-6, hipR=8, kneeL=6, kneeR=4),
              dict(lean=-5, headPitch=8, shL=10, shR=10, elL=25, elR=25, abL=14, abR=14, hipL=-4, hipR=6, kneeL=4, kneeR=3)],
    'crouch': [dict(crouch=2.4, hipL=30, hipR=18, kneeL=55, kneeR=42, footL=-20, footR=-14, lean=10, shL=20, shR=-10, elL=30, elR=20)],
    'jump': [dict(crouch=-0.5, hipL=44, hipR=-10, kneeL=62, kneeR=30, lean=8, shL=-35, shR=40, elL=30, elR=30, abL=20, abR=20)],
}
