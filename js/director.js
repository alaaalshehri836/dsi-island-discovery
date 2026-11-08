// ============================================================================
// The Director — the whole cinematic as a pure function of time t (seconds).
// stateAt(t) returns everything the renderer needs: camera, explorer, boat,
// portal intensity, grading, captions, overlays. Being a pure function makes
// the film seekable (?t=12.3) and guarantees the final frame is reproducible.
// ============================================================================
import { WORLD, pathZ } from './world.js';
import { clamp, lerp, ease, prog } from './util.js';

const D2R = Math.PI / 180;
const yawTo = (cx, cz, tx, tz) => Math.atan2(tx - cx, tz - cz);
const STRIDE = 36; // world units per full walk cycle (two steps)

// ---------------------------------------------------------------- boat
export function boatAt(t) {
  const x = lerp(-2760, WORLD.landing.boatStopX, prog(t, 0.6, 5.35, (u) => 1 - Math.pow(1 - u, 2.2)));
  const moving = t < 5.35;
  const bob = Math.sin(t * 2.4) * (moving ? 1.2 : 0.6) + (t > 5.35 ? -1.2 : 0);
  return { x, z: WORLD.landing.z, y: bob, tilt: Math.sin(t * 2.4 + 1) * 0.03, moving };
}

// ---------------------------------------------------------------- explorer track
// Walk segments: x0->x1 between t0 and t1 (eased at ends when flagged).
const WALKS = [
  { t0: 5.95, t1: 6.9, x0: -1736, x1: -1704, z: 4, print: true },
  { t0: 7.65, t1: 9.05, x0: -1688, x1: -1640, z: 4, print: true },
  { t0: 9.05, t1: 10.65, x0: -1588, x1: -1534, path: true },
  { t0: 10.65, t1: 11.95, x0: -1474, x1: -1430, path: true },
  { t0: 11.95, t1: 13.0, x0: -1400, x1: -1364, path: true },
  { t0: 13.0, t1: 14.5, x0: -1292, x1: -1241, path: true },
  { t0: 14.5, t1: 15.75, x0: -1092, x1: -1046, path: true, easeOut: true },
];
export const FINAL = { charX: -1046, charZ: 0 };

function walkPos(w, t) {
  let u = clamp((t - w.t0) / (w.t1 - w.t0));
  if (w.easeOut) u = 1 - Math.pow(1 - u, 1.6);
  const x = lerp(w.x0, w.x1, u);
  return { x, z: w.path ? pathZ(x) : w.z };
}
export function charAt(t) {
  const B = boatAt(t);
  // in the boat
  if (t < 5.45) return { x: B.x - 16, z: B.z + 2, y: B.y + 7, heading: 90 * D2R, anim: 'idle', frame: Math.floor(t * 1.6) % 2, inBoat: true };
  // jump out onto the sand
  if (t < 5.95) {
    const u = prog(t, 5.45, 5.85);
    const x = lerp(B.x - 6, -1736, u);
    const y = lerp(B.y + 9, 0, u) + Math.sin(Math.PI * u) * 16;
    return { x, z: 3, y: t < 5.85 ? y : 0, heading: 90 * D2R, anim: t < 5.85 ? 'jump' : 'idle', frame: 0 };
  }
  for (const w of WALKS) {
    if (t >= w.t0 && t < w.t1) {
      const p = walkPos(w, t);
      const dist = Math.abs(p.x - w.x0);
      const ph = (dist / STRIDE) % 1;
      return { ...p, y: 0, heading: 90 * D2R, anim: 'walk', frame: Math.floor(ph * 8) };
    }
  }
  // look around on the beach (turns toward camera, scans left/right)
  if (t >= 6.9 && t < 7.65) {
    const u = (t - 6.9) / 0.75;
    const heading = lerp(90, 168, prog(t, 6.9, 7.05, ease.out)) * D2R;
    const f = u < 0.25 ? 3 : u < 0.5 ? 0 : u < 0.75 ? 3 : 2;
    return { x: -1704, z: 4, y: 0, heading, anim: t < 7.05 ? 'idle' : 'look', frame: f };
  }
  // stop and react in front of the portal, then stand still (final pose)
  if (t >= 15.75) {
    const anim = t < 16.05 ? 'react' : t < 17.9 ? 'react' : 'idle';
    const frame = anim === 'react' ? (t < 16.05 ? 0 : 1) : (t >= 20 ? 0 : Math.floor(t * 1.4) % 2);
    return { x: FINAL.charX, z: FINAL.charZ, y: 0, heading: 90 * D2R, anim, frame };
  }
  return { x: -1704, z: 4, y: 0, heading: 90 * D2R, anim: 'idle', frame: 0 };
}

// footstep events (sound + footprints), derived from the walk segments
export function buildSteps() {
  const steps = [];
  for (const w of WALKS) {
    const len = Math.abs(w.x1 - w.x0);
    for (let d = STRIDE * 0.25, i = 0; d < len; d += STRIDE / 2, i++) {
      // invert position->time for the segment
      let lo = w.t0, hi = w.t1;
      for (let k = 0; k < 24; k++) { const m = (lo + hi) / 2; if (Math.abs(walkPos(w, m).x - w.x0) < d) lo = m; else hi = m; }
      const p = walkPos(w, lo);
      steps.push({ t: lo, x: p.x + 2, z: p.z + (i % 2 ? 3 : -3), print: !!w.print });
    }
  }
  steps.push({ t: 5.85, x: -1736, z: 0, print: true }, { t: 5.85, x: -1734, z: 6, print: true });
  return steps.sort((a, b) => a.t - b.t);
}

// ---------------------------------------------------------------- portal light
export function portalAt(t) {
  let I = 0;
  if (t > 9) I = 0.06;                                  // a faint glimmer on the island
  if (t > 12.4) I = lerp(0.06, 0.22, prog(t, 12.4, 13.2));
  if (t > 14.55) I = lerp(0.22, 1.0, prog(t, 14.55, 16.0, ease.inOut));
  const pulse = t > 14.55 ? 0.06 * Math.sin(t * 2.6) : 0;
  return clamp(I + pulse * I);
}

// ---------------------------------------------------------------- shots
const SKY = { skyTop: [56, 118, 204], skyMid: [104, 178, 230], skyHor: [200, 234, 240] };
const JUNGLE_GRADE = { mul: '#d7e4cf', mulAmt: 1, vignette: 0.5 };
const MYSTERY_GRADE = { mul: '#b9c4dc', mulAmt: 1, vignette: 0.62 };

export const SHOTS = [
  { id: 'startup', t0: 0, t1: 1.25, type: 'black' },
  { id: 'vista', t0: 1.25, t1: 3.6, type: 'world', fadeIn: [1.25, 2.15], grade: { vignette: 0.35 },
    cam: (t) => {
      const u = prog(t, 1.25, 3.6, ease.inOut);
      const x = lerp(-3150, -2900, u), z = lerp(-2950, -2700, u);
      return { x, z, h: lerp(620, 470, u), yaw: yawTo(x, z, -1050, 300), hor: lerp(1.32, 0.34, prog(t, 1.25, 3.3, ease.inOut3)), F: 300 };
    }, fog: 5200 },
  { id: 'arrival-wide', t0: 3.6, t1: 5.0, type: 'world', grade: { vignette: 0.38 },
    cam: (t) => {
      const b = boatAt(t);
      const x = b.x - 150 - (t - 3.6) * 10, z = -120;
      return { x, z, h: 30, yaw: yawTo(x, z, b.x + 70, 20), hor: 0.47, F: 290 };
    } },
  { id: 'arrival-side', t0: 5.0, t1: 7.65, type: 'world', grade: { vignette: 0.38 },
    cam: (t) => {
      const b = boatAt(t), c = charAt(t);
      const follow = lerp(b.x + 26, c.x + 16, prog(t, 5.2, 6.4, ease.inOut));
      const F = lerp(280, 340, prog(t, 6.85, 7.65, ease.inOut));
      return { x: follow, z: -175, h: 32, yaw: 0, hor: 0.5, F };
    } },
  { id: 'explore-side', t0: 7.65, t1: 9.05, type: 'world', grade: { vignette: 0.4 },
    cam: (t) => { const c = charAt(t); return { x: c.x + 10 + (t - 7.65) * 6, z: -150, h: 34, yaw: 0, hor: 0.5, F: 290 }; } },
  { id: 'explore-rear', t0: 9.05, t1: 10.65, type: 'world', grade: JUNGLE_GRADE,
    cam: (t) => {
      const c = charAt(t); const x = c.x - 88; const z = pathZ(x) * 0.6;
      return { x, z, h: 40, yaw: yawTo(x, z, c.x + 220, pathZ(c.x + 220)), hor: 0.45, F: 290 };
    }, fog: 2600 },
  { id: 'explore-crane', t0: 10.65, t1: 11.95, type: 'world', grade: { vignette: 0.42 },
    cam: (t) => {
      const u = prog(t, 10.65, 11.95, ease.inOut);
      const c = charAt(t);
      const x = lerp(-1472, -1500, u), z = lerp(-430, -640, u);
      return { x, z, h: lerp(90, 340, u), yaw: yawTo(x, z, c.x + 40, c.z + 260) - 0.1, hor: lerp(0.42, 0.2, u), F: 200 };
    }, fog: 3600 },
  { id: 'notice-closeup', t0: 11.95, t1: 13.0, type: 'portrait', grade: { ...JUNGLE_GRADE, vignette: 0.55 },
    portrait: (t) => {
      const blink = t > 12.22 && t < 12.32;
      const glow = t > 12.5 ? prog(t, 12.5, 12.8) * (0.75 + 0.25 * Math.sin(t * 30)) : 0;
      return { a: blink ? 'blink' : 'lookR', b: 'lookR_glow', mix: glow, zoom: lerp(1.0, 1.06, prog(t, 11.95, 13.0)), glowSide: glow };
    },
    cam: (t) => { const c = charAt(t); return { x: c.x + 30, z: c.z - 60, h: 44, yaw: 0.35, hor: 0.5, F: 520 }; } },
  { id: 'approach', t0: 13.0, t1: 14.5, type: 'world', grade: MYSTERY_GRADE,
    cam: (t) => {
      const c = charAt(t); const x = -1405 + (t - 13) * 8, z = -128;
      return { x, z, h: 64, yaw: yawTo(x, z, c.x + 70, c.z + 6), hor: 0.42, F: 290 };
    }, fog: 2400 },
  { id: 'reveal', t0: 14.5, t1: 16.5, type: 'world', grade: MYSTERY_GRADE,
    cam: (t) => {
      const u = prog(t, 14.5, 16.5, ease.out3);
      const x = lerp(-1240, -1160, u), z = lerp(2, -8, u);
      return { x, z, h: lerp(42, 50, u), yaw: (90 - lerp(0, 2.5, u)) * D2R, hor: 0.43, F: lerp(270, 300, u) };
    }, fog: 2400 },
  { id: 'react-closeup', t0: 16.5, t1: 17.6, type: 'portrait', grade: { ...MYSTERY_GRADE, vignette: 0.6 },
    portrait: (t) => {
      const blink = t > 17.05 && t < 17.14;
      return { a: blink ? 'surprised_blink' : (t < 16.62 ? 'lookR_glow' : 'surprised'), b: null, mix: 0, zoom: lerp(1.0, 1.08, prog(t, 16.5, 17.6, ease.out)), glowSide: 0, glowFront: 1 };
    },
    cam: (t) => ({ x: FINAL.charX + 70, z: 10, h: 44, yaw: -90 * D2R, hor: 0.5, F: 480 }) },
  { id: 'final-ots', t0: 17.6, t1: 99, type: 'world', grade: MYSTERY_GRADE,
    cam: (t) => finalCam(prog(t, 17.6, 20.0, ease.out3)), fog: 2400 },
];
// The final narrative frame (u=1) — see docs/PART2_HANDOFF.md
export function finalCam(u = 1) {
  return {
    x: lerp(-1222, -1190, u), z: lerp(-70, -60, u), h: lerp(64, 60, u),
    yaw: (90 - 14) * D2R, hor: 0.4, F: lerp(290, 300, u),
  };
}

export function shotAt(t) {
  for (let i = SHOTS.length - 1; i >= 0; i--) if (t >= SHOTS[i].t0) return SHOTS[i];
  return SHOTS[0];
}

// ---------------------------------------------------------------- narration & captions
export const LINES = [
  { id: 'n01', text: 'A NEW WORLD IS WAITING…', at: 0.45, pos: 'center', until: 3.05 },
  { id: 'n02', text: 'EVERY JOURNEY BEGINS SOMEWHERE.', at: 4.35, pos: 'top', until: 7.5 },
  { id: 'n03', text: 'SOMETHING IS WAITING FOR YOU…', at: 9.35, pos: 'top', until: 12.7 },
  { id: 'n04', text: 'SOME DISCOVERIES CHANGE EVERYTHING.', at: 14.75, pos: 'top', until: 17.45 },
  { id: 'n05', text: 'THE ADVENTURE IS JUST BEGINNING.', at: 17.65, pos: 'top', until: 19.75 },
  { id: 'n06', text: null, at: 20.25, pos: 'final' },
];
export const END_T = 26.0;
// Keep the narration sequential even with a slower voice
export function scheduleNarration(meta) {
  let prevEnd = 0;
  return LINES.map((l) => {
    const dur = meta?.lines?.[l.id]?.speech ?? 2;
    const at = Math.max(l.at, prevEnd + 0.25);
    prevEnd = at + dur;
    return { ...l, at, dur, until: Math.max(l.until || 0, at + dur + 0.3) };
  });
}

// ---------------------------------------------------------------- ambience levels (0..1) per time
export function ambienceAt(t) {
  const ocean = t < 1.25 ? 0 : t < 9.05 ? lerp(0.15, 0.85, prog(t, 1.25, 3.6)) * (t > 7.65 ? 0.8 : 1) : t < 11.95 ? 0.32 : 0.12;
  const wind = t < 1.25 ? 0 : t < 3.6 ? 0.7 : t < 9 ? 0.45 : t < 13 ? 0.35 : 0.25;
  const jungle = t < 8.6 ? 0 : t < 13 ? 0.7 : lerp(0.5, 0.18, prog(t, 13, 16));
  const hum = t < 13 ? 0 : t < 14.5 ? 0.15 : lerp(0.25, 0.9, prog(t, 14.5, 16.5));
  return { ocean, wind, jungle, hum };
}
