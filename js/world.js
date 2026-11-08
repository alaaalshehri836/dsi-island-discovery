// ============================================================================
// DSI Island — world definition. ONE island, every shot is a camera in it.
// Units: 1 unit = 1 sprite pixel at the "action plane". The explorer is ~46u tall.
// Axes: +X = east, +Z = north, Y = up. Ground is the plane Y = 0.
// ============================================================================
import { mulberry32 } from './util.js';

export const WORLD = {
  island: { cx: 0, cz: 0, R: 1750 },
  beachWidth: 150,
  path: { x0: -1610, x1: -1000, width: 34 },
  plaza: { x: -960, z: 0, r: 125 },
  portal: { x: -880, z: 0, scale: 1.5 },          // faces WEST (toward the arriving explorer)
  landing: { boatStopX: -1795, z: 0 },
  mountain: { x: 760, z: 820, scale: 9 },
  sun: { az: -0.92, el: 0.36 },                     // azimuth (rad, 0 = north, + = east), elevation (rad)
  footprintRegion: { x0: -1770, z0: -80, w: 240, h: 160 },
};

export function coastRadius(theta) {
  const k = 1 + Math.cos(theta); // 0 on the west side -> calm crescent beach there
  return WORLD.island.R + k * (70 * Math.sin(3 * theta + 0.5) + 45 * Math.sin(7 * theta + 1.3) + 22 * Math.sin(13 * theta));
}
// signed distance from coast, + inland
export function coastDist(x, z) {
  const th = Math.atan2(z, x);
  return coastRadius(th) - Math.hypot(x, z);
}
export function pathZ(x) {
  const fade = Math.min(1, Math.max(0, (-1040 - x) / 160));
  return 22 * Math.sin((x + 1600) / 105) * fade;
}

// ---------------------------------------------------------------- terrain map
// Precomputed signed coast distance at 4u/texel over [-2600, 2600]^2.
export const MAP = { min: -2600, cell: 4, n: 1300, d: null };
export function buildMap() {
  const { min, cell, n } = MAP;
  const d = new Float32Array(n * n);
  for (let j = 0; j < n; j++) {
    const z = min + (j + 0.5) * cell;
    for (let i = 0; i < n; i++) {
      const x = min + (i + 0.5) * cell;
      d[j * n + i] = coastDist(x, z);
    }
  }
  MAP.d = d;
}

// ---------------------------------------------------------------- static objects
// Each: {spr: atlas key (or key prefix for animations), x, z, s: scale, flip, anim?: {frames, fps}, kind}
export function buildObjects() {
  const rnd = mulberry32(1234);
  const objs = [];
  const P = WORLD.portal, PL = WORLD.plaza;
  const inCorridor = (x, z, pad = 0) => x > WORLD.path.x0 - 30 && x < WORLD.path.x1 + 40 && Math.abs(z - pathZ(x)) < 48 + pad;
  const inPlaza = (x, z, pad = 0) => Math.hypot(x - PL.x, z - PL.z) < PL.r + 45 + pad;
  // camera clearings (keep cameras out of tree trunks)
  const clear = [[-1420, -128, 70], [-1335, -120, 70], [-1270, -90, 60], [-1175, -10, 40], [-1180, 30, 40], [-1450, -650, 120], [-1478, -430, 95], [-1490, -540, 95], [-1370, -105, 45], [-1335, -80, 45], [-1300, -58, 40], [-1205, -62, 55], [-1240, -55, 45], [-1150, -45, 45], [-1110, -35, 40]];
  const inClear = (x, z) => clear.some(([cx, cz, r]) => Math.hypot(x - cx, z - cz) < r);
  const landingZone = (x, z) => x < -1560 && Math.abs(z) < 75;
  const ok = (x, z) => !inCorridor(x, z) && !inPlaza(x, z) && !inClear(x, z) && !landingZone(x, z);

  // palms: ring along the back of the beach + a few on the sand
  for (let a = 0; a < Math.PI * 2; a += 0.022 + rnd() * 0.02) {
    const r = coastRadius(a) - (165 + rnd() * 90);
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (!ok(x, z)) continue;
    objs.push({ spr: 'palm' + Math.floor(rnd() * 4), anim: { frames: 6, fps: 4 + rnd() * 2, off: rnd() * 6 }, x, z, s: 1.05 + rnd() * 0.35, flip: rnd() < 0.5, kind: 'palm' });
  }
  // hand-placed hero palms framing the landing beach
  for (const [x, z, v, s, f] of [[-1612, 92, 1, 1.3, 0], [-1590, -96, 3, 1.25, 1], [-1655, 175, 0, 1.2, 1], [-1640, -190, 2, 1.35, 0], [-1580, 56, 3, 1.15, 1], [-1575, -60, 0, 1.2, 0], [-1700, 260, 2, 1.25, 0]])
    objs.push({ spr: 'palm' + v, anim: { frames: 6, fps: 5, off: x % 6 }, x, z, s, flip: !!f, kind: 'palm' });

  // jungle trees across the island interior
  for (let gx = -1600; gx < 1700; gx += 62) {
    for (let gz = -1700; gz < 1700; gz += 62) {
      const x = gx + (rnd() - 0.5) * 50, z = gz + (rnd() - 0.5) * 50;
      const d = coastDist(x, z);
      if (d < 270) continue;
      if (!ok(x, z)) continue;
      // thin out far away from the action to keep draw counts sane
      const far = x > -400 ? 0.45 : 1;
      if (rnd() > far) continue;
      objs.push({ spr: 'jtree' + Math.floor(rnd() * 3), x, z, s: 1.2 + rnd() * 0.6, flip: rnd() < 0.5, kind: 'tree' });
    }
  }
  // undergrowth near the path and plaza (where the camera is close)
  for (let i = 0; i < 520; i++) {
    const x = -1600 + rnd() * 760, z = (rnd() - 0.5) * 520;
    if (coastDist(x, z) < 160) continue;
    if (inCorridor(x, z, -14) || inPlaza(x, z, -30) || inClear(x, z)) continue;
    const k = ['bush0', 'bush1', 'bushdark', 'fern0', 'fern1', 'fernflower', 'fernflower2', 'monstera0', 'monstera1', 'grass1'][Math.floor(rnd() * 10)];
    objs.push({ spr: k, x, z, s: 0.9 + rnd() * 0.5, flip: rnd() < 0.5, kind: 'plant' });
  }
  // path edge ferns (frame the rear-follow shots)
  for (let x = -1590; x < -1060; x += 20 + rnd() * 26) {
    for (const side of [-1, 1]) {
      const z = pathZ(x) + side * (30 + rnd() * 16);
      if (side < 0 && x > -1215) continue; // keep the final over-the-shoulder view clear
      const k = ['fern0', 'fern1', 'fernflower', 'grass1', 'monstera0', 'fernflower2'][Math.floor(rnd() * 6)];
      objs.push({ spr: k, x, z, s: 0.8 + rnd() * 0.4, flip: side < 0, kind: 'plant' });
    }
  }
  // foliage that "parts" during the portal reveal dolly (camera passes between these)
  for (const [x, z, k, s] of [[-1222, -24, 'monstera1', 1.25], [-1215, 26, 'fern1', 1.4], [-1196, 30, 'fernflower', 1.1], [-1150, 40, 'monstera0', 1.2]])
    objs.push({ spr: k, x, z, s, flip: z < 0, kind: 'plant' });
  // beach details
  for (let i = 0; i < 60; i++) {
    const a = Math.PI + (rnd() - 0.5) * 1.3;
    const r = coastRadius(a) - (20 + rnd() * 120);
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (landingZone(x, z) && Math.abs(z) < 40) continue;
    const k = ['shells', 'beachgrass', 'rock3', 'shells', 'grass0'][Math.floor(rnd() * 5)];
    objs.push({ spr: k, x, z, s: 1, flip: rnd() < 0.5, kind: 'deco' });
  }
  objs.push({ spr: 'rock0', x: -1712, z: 128, s: 1.4, kind: 'rock' });
  objs.push({ spr: 'rockbig', x: -1770, z: -205, s: 1.3, kind: 'rock' });
  objs.push({ spr: 'rock1', x: -1735, z: 210, s: 1.2, kind: 'rock' });
  objs.push({ spr: 'rock2', x: -1806, z: 160, s: 1.2, kind: 'rock' });
  objs.push({ spr: 'driftwood', x: -1672, z: 64, s: 1.1, kind: 'deco' });
  // supplies left by a previous expedition (hint: someone was here before)
  objs.push({ spr: 'crate', x: -1640, z: 78, s: 1.1, kind: 'prop' });
  objs.push({ spr: 'barrel', x: -1626, z: 92, s: 1.0, kind: 'prop' });
  objs.push({ spr: 'crate', x: -1655, z: 96, s: 0.95, kind: 'prop' });
  objs.push({ spr: 'signpost', x: -1590, z: 44, s: 1.15, kind: 'prop' });
  // mysterious hints along the path
  objs.push({ spr: 'runestone', glow: 'runestone_glow', x: -1452, z: pathZ(-1452) + 44, s: 1.25, kind: 'rune' });
  objs.push({ spr: 'pillar0', x: -1250, z: pathZ(-1250) - 52, s: 1.3, kind: 'prop' });
  objs.push({ spr: 'rock0', x: -1330, z: pathZ(-1330) + 50, s: 1.0, kind: 'rock' });
  // ruins around the plaza
  for (let i = 0; i < 9; i++) {
    const a = -2.5 + i * (5.0 / 8);
    if (Math.abs(a) < 0.5) continue;
    const x = PL.x + Math.cos(a + Math.PI) * (PL.r + 18), z = PL.z + Math.sin(a + Math.PI) * (PL.r + 18);
    objs.push({ spr: i % 2 ? 'pillar1' : 'pillar0', x, z, s: 1.3 + (i % 3) * 0.1, kind: 'prop', flip: i % 2 === 0 });
  }
  objs.push({ spr: 'runestone', glow: 'runestone_glow', x: PL.x - 60, z: PL.z - 92, s: 1.1, kind: 'rune' });
  objs.push({ spr: 'runestone', glow: 'runestone_glow', x: PL.x - 52, z: PL.z + 96, s: 1.1, kind: 'rune', flip: true });
  // backdrop mountain
  objs.push({ spr: 'mountain', x: WORLD.mountain.x, z: WORLD.mountain.z, s: WORLD.mountain.scale, kind: 'mountain', noFog: false });
  return objs;
}

// distant scenery on the horizon (panorama, positioned by azimuth)
export const PANORAMA = [
  { spr: 'isle_far0', az: -1.75, el: 0.0, s: 1.0 },
  { spr: 'isle_far1', az: -1.1, el: 0.0, s: 1.0 },
  { spr: 'isle_mid0', az: -0.55, el: 0.0, s: 1.0 },
  { spr: 'isle_far1', az: 0.12, el: 0.0, s: 0.8 },
  { spr: 'isle_far0', az: 2.3, el: 0.0, s: 0.9 },
  { spr: 'isle_far1', az: -2.6, el: 0.0, s: 0.8 },
];
export const CLOUDS = [
  { spr: 'cloud2', az: -1.2, el: 0.2, s: 1.0, v: 0.004 },
  { spr: 'cloud0', az: -0.45, el: 0.3, s: 1.0, v: 0.006 },
  { spr: 'cloud1', az: 0.15, el: 0.16, s: 1.0, v: 0.005 },
  { spr: 'cloud3', az: 0.55, el: 0.26, s: 1.0, v: 0.007 },
  { spr: 'cloud0', az: 1.1, el: 0.22, s: 0.9, v: 0.004 },
  { spr: 'cloud2', az: 1.7, el: 0.3, s: 1.1, v: 0.005 },
  { spr: 'cloud1', az: 2.4, el: 0.18, s: 1.0, v: 0.006 },
  { spr: 'cloud3', az: -2.1, el: 0.24, s: 1.0, v: 0.005 },
  { spr: 'cloud1', az: -0.9, el: 0.55, s: 1.2, v: 0.003 },
  { spr: 'cloud0', az: 0.45, el: 0.7, s: 1.3, v: 0.004 },
];
