// ============================================================================
// DSI Island — Part 1: The Discovery. Boot, scene composition, UI, main loop.
// ============================================================================
import { Assets } from './assets.js';
import { Renderer } from './renderer.js';
import { buildMap, buildObjects, WORLD } from './world.js';
import { SHOTS, shotAt, charAt, boatAt, portalAt, buildSteps, scheduleNarration, END_T, FINAL } from './director.js';
import { AudioEngine } from './audio.js';
import { drawText, wrap, textWidth } from './pixelfont.js';
import { readConfig } from './config.js';
import { clamp, lerp, prog, ease, mulberry32, angDiff } from './util.js';

const cfg = readConfig();
const Q = new URLSearchParams(location.search);
const cv = document.getElementById('stage');
const ui = {
  title: document.getElementById('title'), start: document.getElementById('start'), load: document.getElementById('loadbar'),
  sound: document.getElementById('sound'), replay: document.getElementById('replay'), replayBig: document.getElementById('replay-big'), hud: document.getElementById('hud'),
};
const assets = new Assets();
let R, OBJECTS, STEPS, PLAN, audio;
let mode = 'title';             // 'title' | 'play' | 'still'
let perfBase = 0, filmT = 0, titleT0 = performance.now();

// ---------------------------------------------------------------- dynamic world objects
const D2R = Math.PI / 180;
function charDir(c, cam) {
  const vx = cam.x - c.x, vz = cam.z - c.z;
  const fx = Math.sin(c.heading), fz = Math.cos(c.heading);
  const lx = -fz, lz = fx;
  const yaw = Math.atan2(vx * lx + vz * lz, vx * fx + vz * fz);
  return ((Math.round(yaw / (22.5 * D2R)) % 16) + 16) % 16;
}
function drawShadow(r, p, k, w, alpha = 0.32) {
  const ctx = r.ctx, s = r.s;
  const rx = w * k * s, ry = Math.max(s * 0.8, rx * clamp(r.cam.h / p.depth, 0.08, 0.6));
  ctx.globalAlpha = alpha; ctx.fillStyle = '#1a1a10';
  ctx.beginPath(); ctx.ellipse(r.offX + p.sx * s, p.sy * s, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
}
function drawExplorer(r, c, p, k, alpha, portalI, t) {
  const dir = charDir(c, r.cam);
  const f = assets.char('day', c.anim, c.frame, dir);
  const lift = (c.y || 0) * k;
  if (!c.inBoat) drawShadow(r, p, k, 9, 0.35 * clamp(1 - (c.y || 0) / 40));
  r.blit(f, p.sx, p.sy - lift, k, { alpha });
  // portal light: crossfade to the portal-lit render of the same frame
  const dd = Math.hypot(c.x - WORLD.portal.x, c.z - WORLD.portal.z);
  const pk = portalI * clamp(1.25 - dd / 400);
  if (pk > 0.02) r.blit(assets.char('portal', c.anim, c.frame, dir), p.sx, p.sy - lift, k, { alpha: alpha * clamp(pk) });
}
function dynamicObjects(t, st) {
  const out = [];
  const c = charAt(t), b = boatAt(t);
  // boat with the explorer standing inside it
  out.push({ x: b.x, z: b.z, y: b.y, s: 1, noNearFade: false, draw: (r, p, k, alpha) => {
    const bob = b.y * k;
    // wake / foam when moving
    if (b.moving) {
      const ctx = r.ctx, s = r.s;
      ctx.fillStyle = '#eafaf6';
      const rr = mulberry32(Math.floor(t * 12));
      for (let i = 0; i < 26; i++) {
        const wx = -48 - rr() * 70, wy = (rr() - 0.5) * 6;
        ctx.globalAlpha = 0.5 + rr() * 0.5;
        ctx.fillRect(Math.round(r.offX + (p.sx + wx * k) * s), Math.round((p.sy + wy * k * 0.3) * s), Math.ceil(k * s * 1.5), Math.ceil(k * s));
      }
      ctx.globalAlpha = 1;
    }
    r.blit(assets.env('boat_back'), p.sx, p.sy - bob, k, { alpha });
    if (c.inBoat) {
      const pc = r.project(c.x, 0, c.z);
      if (pc) r.blit(assets.char('day', c.anim, c.frame, charDir(c, r.cam)), pc.sx, pc.sy - (c.y) * pc.k, pc.k, { alpha });
    }
    r.blit(assets.env('boat_front'), p.sx, p.sy - bob, k, { alpha });
  } });
  if (!c.inBoat && st.showChar !== false) out.push({ x: c.x, z: c.z, s: 1, noNearFade: true, draw: (r, p, k, alpha) => drawExplorer(r, c, p, k, 1, st.portalI, t) });
  // the portal
  const P = WORLD.portal;
  out.push({ x: P.x, z: P.z, s: P.scale, draw: (r, p, k) => {
    const I = st.portalI;
    const vx = r.cam.x - P.x, vz = r.cam.z - P.z, vl = Math.hypot(vx, vz) || 1;
    const face = Math.max(0.2, Math.abs(-vx / vl));
    const fr = assets.env('portal');
    const cy = p.sy - 35 * k;
    if (t < 12.9) { // not revealed yet: only a faint glimmer between the trees
      r.blit(assets.env('glow_blue'), p.sx, cy, k * 1.3, { alpha: 0.35 * I * (0.7 + 0.3 * Math.sin(t * 5)), blend: 'lighter' });
      return;
    }
    r.blit(fr, p.sx, p.sy, k, { sx: face });
    if (I > 0.01) {
      const ef = assets.env('portal_energy_' + (Math.floor(t * 10) % 12));
      r.blit(ef, p.sx, cy + 0.5 * k, k, { sx: face, alpha: clamp(I * 1.5) });
      r.blit(assets.env('portal_runes'), p.sx, p.sy, k, { sx: face, alpha: clamp(I * 1.2), blend: 'lighter' });
      const g = assets.env('glow_blue');
      r.blit(g, p.sx, cy + 48 * k * 0.0, k * 1.15, { alpha: 0.5 * I * (0.9 + 0.1 * Math.sin(t * 4)), blend: 'lighter' });
      r.blit(g, p.sx, cy, k * 2.6, { alpha: 0.22 * I, blend: 'lighter' });
    }
  } });
  // floating pixel particles around the portal + a few fireflies on the path
  const I = st.portalI;
  if (I > 0.04) {
    for (let i = 0; i < 70; i++) {
      const rr = mulberry32(i * 97 + 3);
      const life = 3 + rr() * 3, ph = ((t + rr() * life) % life) / life;
      const a = rr() * Math.PI * 2, rad = 20 + rr() * 90;
      const x = P.x - 10 + Math.cos(a) * rad * 0.6, z = P.z + Math.sin(a) * rad;
      const y = 4 + ph * (60 + rr() * 70) + Math.sin(t * 2 + i) * 3;
      const sz = rr() < 0.3 ? 2 : 1.2;
      const alpha = Math.sin(Math.PI * ph) * clamp(I * 1.6 - 0.1 * (i % 3));
      if (i > 18 + I * 52) continue;
      out.push({ x, z, s: 1, y, noNearFade: true, draw: (r, p, k) => {
        const ctx = r.ctx, s = r.s, d = Math.max(1, Math.round(sz * k * s));
        ctx.globalAlpha = alpha; ctx.fillStyle = rr() < 0.5 ? '#bff6ff' : '#5fd0ff';
        ctx.globalCompositeOperation = 'lighter';
        ctx.fillRect(Math.round(r.offX + p.sx * s), Math.round((p.sy) * s), d, d);
        ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
      } });
    }
  }
  if (t > 9 && t < 17.6) {
    for (let i = 0; i < 24; i++) {
      const rr = mulberry32(i * 31 + 7);
      const x = -1560 + rr() * 520, z = (rr() - 0.5) * 140, y = 12 + rr() * 40 + Math.sin(t * 1.3 + i) * 6;
      const tw = 0.5 + 0.5 * Math.sin(t * (2 + rr() * 3) + i * 4);
      out.push({ x: x + Math.sin(t * 0.7 + i) * 8, z, y, s: 1, noNearFade: true, draw: (r, p, k) => {
        const ctx = r.ctx, s = r.s, d = Math.max(1, Math.round(1.3 * k * s));
        ctx.globalAlpha = tw * 0.9; ctx.fillStyle = i % 4 ? '#e8ff9a' : '#8ff0ff'; ctx.globalCompositeOperation = 'lighter';
        ctx.fillRect(Math.round(r.offX + p.sx * s), Math.round(p.sy * s), d, d);
        ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
      } });
    }
  }
  return out;
}

// ---------------------------------------------------------------- composition of one frame
const SKY = { skyTop: [56, 118, 204], skyMid: [104, 178, 230], skyHor: [200, 234, 240] };
function renderFrame(t, opts = {}) {
  const ctx = R.ctx;
  ctx.fillStyle = '#05060c'; ctx.fillRect(0, 0, cv.width, cv.height);
  const shot = opts.shot || shotAt(t);
  if (shot.type === 'black') { drawStartup(t); }
  else {
    const cam = shot.cam(t);
    R.setCamera(cam);
    const st = { t, portalI: portalAt(t), fog: shot.fog || 4600, ...SKY, runeGlow: t > 9 ? 0.5 + portalAt(t) * 0.5 : 0, sunGlow: 1 };
    if (shot.type === 'portrait') st.showChar = false;
    R.stampFootprints(STEPS, t);
    R.drawGround(st);
    R.drawPanorama(st);
    R.drawBillboards(st, OBJECTS.concat(dynamicObjects(t, st)));
    if (shot.type === 'portrait') drawPortrait(shot.portrait(t), t, st);
    R.grade(shot.grade || {});
    if (shot.fadeIn) R.ditherFill(1 - prog(t, shot.fadeIn[0], shot.fadeIn[1]));
    // short dithered "blink" on every hard cut (feels like a game camera switch)
    const sinceCut = t - shot.t0;
    if (!shot.fadeIn && sinceCut < 0.12 && shot.t0 > 0 && !opts.noCutFx) R.ditherFill(0.5 * (1 - sinceCut / 0.12));
  }
  if (!opts.hideText) { drawCaptions(t); drawFinal(t); }
}

function drawPortrait(p, t, st) {
  const ctx = R.ctx, s = R.s;
  // separate the subject from the tele background
  ctx.fillStyle = 'rgba(10,18,24,0.35)'; ctx.fillRect(0, 0, cv.width, cv.height);
  const k = (Math.min(R.VH * 0.62, R.VW * 0.95) / 72) * p.zoom;
  const x = R.VW / 2 + 6, y = R.VH + 4 * k;
  const fa = assets.portrait(p.a);
  R.blit(fa, x, y, k);
  if (p.b && p.mix > 0) R.blit(assets.portrait(p.b), x, y, k, { alpha: clamp(p.mix) });
  // light cast by the (still unseen) portal
  if (p.glowSide > 0) {
    const g = ctx.createLinearGradient(cv.width, 0, cv.width * 0.45, 0);
    g.addColorStop(0, `rgba(80,190,255,${0.35 * p.glowSide})`); g.addColorStop(1, 'rgba(80,190,255,0)');
    ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = g; ctx.fillRect(0, 0, cv.width, cv.height); ctx.globalCompositeOperation = 'source-over';
  }
  if (p.glowFront) {
    const pulse = 0.85 + 0.15 * Math.sin(t * 5);
    ctx.globalCompositeOperation = 'lighter';
    ctx.fillStyle = `rgba(40,120,220,${0.18 * pulse})`; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.globalCompositeOperation = 'source-over';
    // drifting motes in front of the face
    for (let i = 0; i < 26; i++) {
      const rr = mulberry32(i * 13 + 1); const ph = (t * (0.15 + rr() * 0.2) + rr()) % 1;
      const px = (rr() * R.VW), py = R.VH * (1 - ph);
      const d = Math.max(1, Math.round(s * (rr() < 0.3 ? 2 : 1)));
      ctx.globalAlpha = Math.sin(Math.PI * ph) * 0.9; ctx.fillStyle = '#bff6ff';
      ctx.fillRect(Math.round(R.offX + px * s), Math.round(py * s), d, d);
    }
    ctx.globalAlpha = 1;
  }
}

function drawStartup(t) {
  const ctx = R.ctx, W = cv.width, Hh = cv.height, s = R.s;
  // CRT power-on line
  if (t < 0.5) {
    const u = prog(t, 0, 0.22, ease.out3), v = 1 - prog(t, 0.22, 0.5);
    const lw = W * u, lh = Math.max(1, Math.round(s * (1 + 2 * (1 - u))));
    ctx.globalAlpha = v; ctx.fillStyle = '#dff8ff';
    ctx.fillRect((W - lw) / 2, Hh * 0.5 - lh / 2, lw, lh);
    ctx.globalAlpha = v * 0.35; ctx.fillRect((W - lw * 0.6) / 2, Hh * 0.5 - lh * 3, lw * 0.6, lh * 6);
    ctx.globalAlpha = 1;
  }
  // a single blinking cursor waiting
  if (t > 0.25 && t < 0.45 && Math.floor(t * 12) % 2) {
    ctx.fillStyle = '#f2cf73'; const px = Math.max(1, Math.round(s * 1.5));
    ctx.fillRect(Math.round(W / 2 - 3 * px), Math.round(Hh * 0.45), px * 5, px * 7);
  }
}

// ---------------------------------------------------------------- captions
function captionPx() { return Math.max(1, Math.round(R.s * 1.5)); }
function drawCaptions(t) {
  if (!PLAN) return;
  const ctx = R.ctx, s = R.s, px = captionPx();
  for (const l of PLAN.lines) {
    if (!l.text || t < l.at - 0.05 || t > l.until) continue;
    const reveal = Math.floor((t - l.at + 0.05) * 32);
    const alpha = 1 - prog(t, l.until - 0.35, l.until);
    const maxW = Math.floor(((Math.min(R.VW, 300) - 22) * s) / px);
    const lines = wrap(l.text, maxW);
    const lh = 11 * px;
    let y = l.pos === 'center' ? cv.height * 0.44 - (lines.length * lh) / 2 : Math.max(cv.height * 0.085, R.s * 22);
    // soft dark band behind top captions for legibility
    if (l.pos === 'top') {
      const g = ctx.createLinearGradient(0, 0, 0, y + lines.length * lh + 18 * s);
      g.addColorStop(0, `rgba(4,8,18,${0.55 * alpha})`); g.addColorStop(1, 'rgba(4,8,18,0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, cv.width, y + lines.length * lh + 18 * s);
    }
    let shown = reveal;
    for (const ln of lines) {
      drawText(ctx, ln, cv.width / 2, y, px, { reveal: shown, alpha });
      shown -= ln.length + 1; y += lh;
    }
  }
}
// ---------------------------------------------------------------- final announcement (scene 05)
function drawFinal(t) {
  const T0 = 19.75;
  if (t < T0) return;
  const ctx = R.ctx, s = R.s, W = cv.width, Hh = cv.height;
  const a0 = prog(t, T0, T0 + 0.8);
  // darken the sky area for a clean title composition (portal glow stays visible below)
  const g = ctx.createLinearGradient(0, 0, 0, Hh * 0.62);
  g.addColorStop(0, `rgba(3,6,16,${0.86 * a0})`); g.addColorStop(0.7, `rgba(3,6,16,${0.55 * a0})`); g.addColorStop(1, 'rgba(3,6,16,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, Hh * 0.62);
  const topY = Math.max(R.VH * 0.06, 16);
  // DSI logo with a pixel shine sweep
  const logo = assets.env('dsi_logo');
  const la = prog(t, T0 + 0.2, T0 + 0.9);
  const lk = Math.max(1, Math.floor(Math.min((R.VW - 30) / logo.w, 1.0) * s)) / s;
  const lw = logo.w * lk, ly = topY + logo.h * lk;
  if (la > 0) {
    R.blit(assets.env('glow_blue'), R.VW / 2, ly - logo.h * lk * 0.5 + 2, lk * 2.0, { alpha: 0.45 * la * (0.85 + 0.15 * Math.sin(t * 3)), blend: 'lighter' });
    R.blit({ ...logo, ax: logo.w / 2, ay: logo.h }, R.VW / 2, ly + (1 - la) * 6, lk, { alpha: la });
    // shine sweep
    const sw = prog(t, T0 + 0.9, T0 + 1.6);
    if (sw > 0 && sw < 1) {
      const x0 = R.offX + (R.VW / 2 - lw / 2 + sw * lw) * s;
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.55; ctx.fillStyle = '#fff6d0';
      const yy = (ly - logo.h * lk) * s;
      for (let i = 0; i < 4; i++) ctx.fillRect(Math.round(x0 + i * s * 2 - (ly - yy) * 0.3), Math.round(yy), Math.ceil(s), Math.round(logo.h * lk * s));
      ctx.restore();
    }
  }
  const y = ly * s + 10 * s;
  // MEET US AT DSI! — the only text on the final screen
  const big = Math.max(1, Math.round(s * Math.min(2.4, (R.VW - 20) / textWidth('MEET US AT DSI!'))));
  const ma = prog(t, T0 + 0.45, T0 + 0.9);
  if (ma > 0) drawText(ctx, 'MEET US AT DSI!', W / 2, y + (1 - ma) * 4 * s, big, { reveal: Math.floor((t - T0 - 0.45) * 30), fill: ['#ffffff', '#f6d36a', '#e0a23a'] });
}

// ---------------------------------------------------------------- sound plan
function buildPlan(narrMeta) {
  const lines = scheduleNarration(narrMeta);
  const sfx = [{ t: 0.0, key: 'startup', gain: 0.8 }, { t: 5.3, key: 'boat', gain: 0.9 }, { t: 5.36, key: 'splash', gain: 0.5 },
    { t: 5.85, key: 'land', gain: 0.8 }, { t: 14.5, key: 'reveal', gain: 1.0 }];
  for (const l of lines) if (l.text) sfx.push({ t: l.at - 0.05, key: 'chime', gain: 0.35 });
  sfx.push({ t: 20.05, key: 'chime', gain: 0.5 });
  STEPS.forEach((s, i) => sfx.push({ t: s.t, key: 'step' + (i % 4), gain: s.t > 13 ? 0.42 : 0.55, pan: (i % 2 ? 0.08 : -0.08) }));
  return { lines, sfx };
}

// ---------------------------------------------------------------- main loop & UI
function now() {
  const c = audio && audio.clock();
  return c != null ? c : (performance.now() - perfBase) / 1000;
}
function loop() {
  if (mode === 'title') {
    const tt = (performance.now() - titleT0) / 1000;
    // a calm, dimmed establishing view behind the title (no spoilers)
    const shot = SHOTS[1];
    renderFrame(3.3 + Math.sin(tt * 0.2) * 0.25, { shot, hideText: true, noCutFx: true });
    R.ditherFill(0.5, '#05060c');
  } else if (mode === 'play') {
    filmT = now();
    renderFrame(filmT);
    if (filmT > END_T && ui.replayBig.hidden) { ui.replayBig.hidden = false; }
  }
  requestAnimationFrame(loop);
}
async function startFilm(from = 0) {
  ui.title.classList.add('gone'); ui.hud.hidden = false; ui.replayBig.hidden = true;
  await audio.unlock();
  audio.start(from, PLAN);
  perfBase = performance.now() - from * 1000;
  mode = 'play';
}
function pixelLabel(el, text, scale = 2, fill) {
  const c = document.createElement('canvas');
  const w = textWidth(text) + 4, h = 11;
  c.width = w * scale; c.height = h * scale;
  const x = c.getContext('2d');
  drawText(x, text, c.width / 2, scale * 1, scale, { fill, shadow: null });
  el.appendChild(c);
}
async function boot() {
  R = new Renderer(cv, null);
  addEventListener('resize', () => R.resize());
  buildMap();
  OBJECTS = buildObjects();
  STEPS = buildSteps();
  await assets.load((p) => ui.load.style.setProperty('--p', (p * 0.6).toFixed(3)));
  R.A = assets;
  drawTitleLogo();
  let narrMeta = null;
  try { const m = await (await fetch('assets/audio/narration/narration.json')).json(); narrMeta = m[cfg.voice]; } catch (e) {}
  PLAN = buildPlan(narrMeta);
  window.__DSI = { renderFrame, PLAN, SHOTS, R, FINAL };
  // still frame mode for testing / Part 2 hand-off: ?t=12.3  or  ?frame=final
  if (Q.has('t') || Q.get('frame') === 'final') {
    const t = Q.get('frame') === 'final' ? 22 : parseFloat(Q.get('t'));
    ui.title.style.display = 'none';
    mode = 'still';
    const draw = () => { renderFrame(t, { hideText: Q.get('frame') === 'final' || Q.has('notext') }); };
    draw(); addEventListener('resize', draw);
    document.body.dataset.ready = '1';
    return;
  }
  audio = new AudioEngine(cfg.voice);
  await audio.preload(PLAN.lines, (p) => ui.load.style.setProperty('--p', (0.6 + p * 0.4).toFixed(3)));
  ui.load.style.setProperty('--p', '1');
  document.body.classList.add('loaded');
  ui.start.disabled = false;
  document.body.dataset.ready = '1';
  requestAnimationFrame(loop);
}

function drawTitleLogo() {
  const c = document.getElementById('title-logo');
  const logo = assets.env('dsi_logo');
  const W = 150, H = 92; c.width = W * 4; c.height = H * 4;
  const x = c.getContext('2d'); x.imageSmoothingEnabled = false; x.scale(4, 4);
  x.drawImage(logo.img, logo.x, logo.y, logo.w, logo.h, Math.round((W - logo.w) / 2), 2, logo.w, logo.h);
  drawText(x, 'ISLAND', W / 2, logo.h + 6, 3, { fill: ['#e6fbff', '#9fe6ff', '#4fb4ea'], outline: '#06142a' });
  drawText(x, 'PART 1 · THE DISCOVERY', W / 2, logo.h + 34, 1, { fill: ['#fff6d6', '#f2cf73', '#d99a3a'] });
}
pixelLabel(document.getElementById('hint'), 'BEST WITH SOUND ON', 2, ['#c8d6e6', '#9fb3c8', '#8098b0']);
pixelLabel(ui.start, 'START ADVENTURE', 3);
pixelLabel(ui.replayBig, 'REPLAY', 3);
ui.start.disabled = true;
ui.start.addEventListener('click', () => { if (!ui.start.disabled) { startFilm(0).then(() => audio.click()); } });
ui.replay.addEventListener('click', () => { audio.click(); startFilm(0); });
ui.replayBig.addEventListener('click', () => { audio.click(); startFilm(0); });
ui.sound.addEventListener('click', () => {
  const m = !audio.muted; audio.setMuted(m); ui.sound.classList.toggle('muted', m); ui.sound.setAttribute('aria-pressed', String(m));
});
document.addEventListener('visibilitychange', () => {
  if (!audio || !audio.ctx) return;
  if (document.hidden) audio.ctx.suspend(); else audio.ctx.resume();
});
boot().catch((e) => { console.error(e); document.getElementById('err').textContent = 'Failed to load: ' + e.message; });
