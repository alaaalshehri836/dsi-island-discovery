// ============================================================================
// Retro "Mode 7" ground + billboard sprite renderer.
// The ground/sea/sky are rendered per virtual pixel into a low-res buffer
// (crisp, chunky 16-bit pixels); sprites are drawn with nearest-neighbour
// scaling on top. Virtual safe area is 180x320 (9:16); wider/taller screens
// simply see more of the same world.
// ============================================================================
import { WORLD, MAP, pathZ, PANORAMA, CLOUDS } from './world.js';
import { clamp, hash2, BAYER4, angDiff, lerp } from './util.js';

export const SAFE_W = 180, SAFE_H = 320, MAX_VW = 600;
const pack = (r, g, b) => (255 << 24) | (b << 16) | (g << 8) | r;
const H = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const C = (h) => H(h);
// palette ---------------------------------------------------------------
const WATER = ['#0a4170', '#0d5f8f', '#127fa4', '#1aa4b0', '#36c6bf', '#6fe2d0'].map(C);
const FOAM = C('#f2fbf6'), FOAM2 = C('#c4f2e8'), WAVEHI = C('#b9f3ec'), GLINT = C('#fff3c2');
const WET = [C('#ad8d5e'), C('#9c7e52')], SAND = [C('#f2dcaa'), C('#e9cd95'), C('#dcbd82')], SPECK = C('#c7a46c'), SHELL = C('#fff1e2');
const GRASS = [C('#6aa244'), C('#558e38'), C('#43772f')], JUNGLE = [C('#2c5a2e'), C('#234a28'), C('#1a3a20'), C('#3f6a2c')];
const PATHC = [C('#c4a272'), C('#b39264'), C('#9e7f55'), C('#8a6e4a')];
const STONE = [C('#9696a6'), C('#80809a'), C('#6a6a84'), C('#45455c')], RUNE = C('#6ed6ff');
const FOOT = C('#c9a56f');

export class Renderer {
  constructor(canvas, assets) {
    this.cv = canvas; this.ctx = canvas.getContext('2d', { alpha: false });
    this.A = assets; this.tintCache = new Map();
    this.low = document.createElement('canvas'); this.lctx = this.low.getContext('2d');
    this.foot = new Uint8Array(WORLD.footprintRegion.w * WORLD.footprintRegion.h);
    this.footKey = -1;
    this.resize();
  }
  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const cw = Math.max(1, Math.round(this.cv.clientWidth * dpr)), ch = Math.max(1, Math.round(this.cv.clientHeight * dpr));
    this.cv.width = cw; this.cv.height = ch;
    this.s = Math.min(cw / SAFE_W, ch / SAFE_H);
    this.VW = Math.min(MAX_VW, Math.ceil(cw / this.s)); this.VH = Math.ceil(ch / this.s);
    this.offX = Math.round((cw - this.VW * this.s) / 2); this.offY = 0;
    this.low.width = this.VW; this.low.height = this.VH;
    this.img = this.lctx.createImageData(this.VW, this.VH);
    this.buf = new Uint32Array(this.img.data.buffer);
    this.ctx.imageSmoothingEnabled = false;
  }

  // ------------------------------------------------------------ camera math
  setCamera(c) {
    this.cam = c;
    this.fx = Math.sin(c.yaw); this.fz = Math.cos(c.yaw);
    this.rx = Math.cos(c.yaw); this.rz = -Math.sin(c.yaw);
    this.hy = c.hor * this.VH; // horizon row (virtual px)
  }
  project(x, y, z) {
    const c = this.cam, dx = x - c.x, dz = z - c.z;
    const depth = dx * this.fx + dz * this.fz;
    if (depth < 1) return null;
    const lat = dx * this.rx + dz * this.rz;
    const k = c.F / depth;
    return { sx: this.VW / 2 + lat * k, sy: this.hy + (c.h - y) * k, k, depth };
  }

  // ------------------------------------------------------------ footprints
  stampFootprints(steps, t) {
    const n = steps.filter((s) => s.t <= t).length;
    if (n === this.footKey) return;
    this.footKey = n; this.foot.fill(0);
    const R = WORLD.footprintRegion;
    for (let i = 0; i < n; i++) {
      const s = steps[i];
      if (!s.print) continue;
      const cx = Math.round(s.x - R.x0), cz = Math.round(s.z - R.z0);
      for (let dz = -2; dz <= 2; dz++) for (let dx = -4; dx <= 3; dx++) {
        if ((dx * dx) / 16 + (dz * dz) / 5 > 1) continue;
        const px = cx + dx, pz = cz + dz;
        if (px >= 0 && pz >= 0 && px < R.w && pz < R.h) this.foot[pz * R.w + px] = 1;
      }
    }
  }

  // ------------------------------------------------------------ sky + ground
  drawGround(st) {
    const { VW, VH, buf } = this; const c = this.cam; const t = st.t;
    const hy = this.hy, F = c.F;
    const map = MAP.d, mn = MAP.min, cell = MAP.cell, N = MAP.n;
    const PI = WORLD.portal, PLZ = WORLD.plaza, FR = WORLD.footprintRegion;
    const portalI = st.portalI || 0;
    const fogD = st.fog || 4200;
    const haze = st.haze || [190, 226, 236];
    const sunAz = WORLD.sun.az, sunEl = WORLD.sun.el;
    const skyTop = st.skyTop || [58, 120, 206], skyMid = st.skyMid || [110, 182, 232], skyHor = st.skyHor || [196, 232, 240];
    const sunCol = [255, 230, 170];
    const bw = WORLD.beachWidth;
    // per-column azimuth
    const colAz = new Float32Array(VW);
    for (let x = 0; x < VW; x++) colAz[x] = c.yaw + Math.atan((x + 0.5 - VW / 2) / F);
    for (let y = 0; y < VH; y++) {
      const row = y * VW;
      const by = (y & 3) * 4;
      if (y + 0.5 < hy + 0.5) {
        // ---------------- sky
        const el = (hy - y - 0.5) / F; // approx elevation (rad)
        for (let x = 0; x < VW; x++) {
          const b = BAYER4[by + (x & 3)];
          const e = el + (b - 0.5) * 0.035;
          let r, g, bl;
          if (e < 0.12) { const k = e / 0.12; r = lerp(skyHor[0], skyMid[0], k); g = lerp(skyHor[1], skyMid[1], k); bl = lerp(skyHor[2], skyMid[2], k); }
          else { const k = Math.min(1, (e - 0.12) / 0.6); r = lerp(skyMid[0], skyTop[0], k); g = lerp(skyMid[1], skyTop[1], k); bl = lerp(skyMid[2], skyTop[2], k); }
          // warm sun halo
          const da = angDiff(colAz[x], sunAz), de = el - sunEl;
          const sd = da * da + de * de;
          if (sd < 0.5) { const k = (1 - sd / 0.5); const kk = k * k * 0.55 * (st.sunGlow ?? 1); r = lerp(r, sunCol[0], kk); g = lerp(g, sunCol[1], kk); bl = lerp(bl, sunCol[2], kk); }
          // quantise to give banded retro gradients
          r = (r >> 3) << 3; g = (g >> 3) << 3; bl = (bl >> 3) << 3;
          buf[row + x] = pack(r, g, bl);
        }
        continue;
      }
      // ---------------- ground (mode 7)
      const depth = (c.h * F) / (y + 0.5 - hy);
      const wx0 = c.x + this.fx * depth, wz0 = c.z + this.fz * depth;
      const step = depth / F;
      let fog = depth / (depth + fogD); fog = fog * fog * (st.fogAmt ?? 1);
      const far = depth > 2600;
      for (let x = 0; x < VW; x++) {
        const lat = (x + 0.5 - VW / 2) * step;
        const X = wx0 + this.rx * lat, Z = wz0 + this.rz * lat;
        const ix = Math.floor(X), iz = Math.floor(Z);
        const hsh = hash2(ix, iz);
        const mi = Math.floor((X - mn) / cell), mj = Math.floor((Z - mn) / cell);
        let d = (mi >= 0 && mj >= 0 && mi < N && mj < N) ? map[mj * N + mi] : -3000;
        d += (hsh - 0.5) * 6;
        const b = BAYER4[by + (x & 3)];
        let col;
        if (d < 0) {
          // ---------------- water
          const dd = -d;
          const wv = Math.sin(X * 0.021 + Z * 0.006 + t * 0.9) * 18;
          const q = dd + wv * 0.4 + (b - 0.5) * 22;
          const wi = q < 14 ? 5 : q < 45 ? 4 : q < 140 ? 3 : q < 380 ? 2 : q < 900 ? 1 : 0;
          col = WATER[wi];
          // surf run-up & foam lines
          const run = -14 + 11 * Math.sin(t * 1.4 + Z * 0.004);
          if (d > run - 4) col = FOAM;
          else if (d > run - 8 && hsh > 0.35) col = FOAM2;
          else {
            const brk = -48 - 26 * ((t * 0.32 + Z * 0.0007) % 1);
            if (Math.abs(d - brk) < 2.6 && hsh > 0.25 && dd < 120) col = (hsh > 0.7 ? FOAM : FOAM2);
            else if (!far) {
              const w = Math.sin(X * 0.05 + Z * 0.013 + t * 1.25) + 0.75 * Math.sin(Z * 0.093 - X * 0.021 - t * 0.85) + 0.4 * Math.sin((X + Z) * 0.2 + t * 2.2);
              if (w > 1.62 && hsh > 0.3) col = WAVEHI;
            }
            // golden sun glitter towards the sun
            const da = angDiff(colAz[x], sunAz);
            if (da * da < 0.08 && depth > 120) {
              const g = hash2(Math.floor(X / 3), Math.floor(Z / 3) + Math.floor(t * 7) * 7919);
              if (g > 0.86 + da * da * 1.2) col = GLINT;
            }
          }
        } else {
          // ---------------- land
          const wetEdge = 12 + 8 * Math.sin(t * 1.4 + Z * 0.004 - 0.9);
          if (d < wetEdge) col = WET[hsh > 0.5 ? 1 : 0];
          else if (d < bw + (hsh - 0.5) * 22 + 10 * Math.sin(Z * 0.02)) {
            col = SAND[(hsh * 3) | 0];
            if (hsh > 0.985) col = SPECK; else if (hsh < 0.004) col = SHELL;
            if (d > bw - 30 && hash2(ix >> 2, iz >> 2) > 0.7) col = SAND[2];
          } else if (d < bw + 45 + (hsh - 0.5) * 30) {
            col = GRASS[(hsh * 3) | 0];
          } else {
            const dap = hash2(ix >> 3, iz >> 3);
            col = JUNGLE[dap > 0.82 ? 3 : (hsh * 3) | 0];
          }
          // path
          if (X > WORLD.path.x0 && X < WORLD.path.x1 + 30) {
            const pz = Math.abs(Z - pathZ(X));
            const w = WORLD.path.width / 2 + (hsh - 0.5) * 8 + 3 * Math.sin(X * 0.05);
            if (pz < w) col = PATHC[pz > w - 4 ? 3 : (hsh * 3) | 0];
          }
          // ancient stone plaza
          const pdx = X - PLZ.x, pdz = Z - PLZ.z, pr = Math.sqrt(pdx * pdx + pdz * pdz);
          if (pr < PLZ.r) {
            const rr = PLZ.r - pr;
            if (rr < 4) col = STONE[3];
            else if (Math.abs(pr - 92) < 2.2) col = (Math.sin(Math.atan2(pdz, pdx) * 24) > 0.2 && portalI > 0.05) ? RUNE : STONE[2];
            else {
              const gx = ((X + 2000) % 16 + 16) % 16, gz = ((Z + 2000) % 16 + 16) % 16;
              col = (gx < 1.2 || gz < 1.2) ? STONE[3] : STONE[(hash2(Math.floor((X + 2000) / 16), Math.floor((Z + 2000) / 16)) * 3) | 0];
              if (hsh > 0.93) col = JUNGLE[0];
            }
          }
          // footprints
          const fx = ix - FR.x0, fz = iz - FR.z0;
          if (fx >= 0 && fz >= 0 && fx < FR.w && fz < FR.h && this.foot[fz * FR.w + fx]) col = d < 18 ? WET[1] : FOOT;
        }
        let r = col[0], g = col[1], bb = col[2];
        // portal light on the ground
        if (portalI > 0) {
          const qx = X - PI.x, qz = Z - PI.z;
          const pd2 = qx * qx + qz * qz;
          if (pd2 < 330 * 330) {
            const k0 = 1 - Math.sqrt(pd2) / 330;
            let k = k0 * k0 * portalI * (0.85 + 0.15 * Math.sin(t * 3 - Math.sqrt(pd2) * 0.05));
            k += (b - 0.5) * 0.12;
            if (k > 0.02) { r = lerp(r, 120, k * 0.75); g = lerp(g, 214, k * 0.8); bb = lerp(bb, 255, k * 0.9); }
          }
        }
        // atmospheric haze
        const f = fog + (b - 0.5) * 0.06;
        if (f > 0.01) { r = lerp(r, haze[0], f); g = lerp(g, haze[1], f); bb = lerp(bb, haze[2], f); }
        buf[row + x] = pack(r | 0, g | 0, bb | 0);
      }
    }
    this.lctx.putImageData(this.img, 0, 0);
    this.ctx.drawImage(this.low, 0, 0, this.VW, this.VH, this.offX, this.offY, this.VW * this.s, this.VH * this.s);
  }

  // ------------------------------------------------------------ sprites
  tinted(key, frame, col) {
    const k = key + '|' + col;
    let cv = this.tintCache.get(k);
    if (!cv) {
      cv = document.createElement('canvas'); cv.width = frame.w; cv.height = frame.h;
      const x = cv.getContext('2d');
      x.drawImage(frame.img, frame.x, frame.y, frame.w, frame.h, 0, 0, frame.w, frame.h);
      x.globalCompositeOperation = 'source-in'; x.fillStyle = col; x.fillRect(0, 0, frame.w, frame.h);
      this.tintCache.set(k, cv);
    }
    return cv;
  }
  // draw frame f (atlas rect) with anchor at virtual (sx, sy), scale k (virtual px per sprite px)
  blit(f, sx, sy, k, opts = {}) {
    const s = this.s, ctx = this.ctx;
    const kx = k * (opts.sx || 1);
    const w = f.w * kx * s, h = f.h * k * s;
    const flip = !!opts.flip;
    let dx = this.offX + (sx - (flip ? f.w - f.ax : f.ax) * kx) * s, dy = this.offY + (sy - f.ay * k) * s;
    dx = Math.round(dx); dy = Math.round(dy);
    const dw = Math.max(1, Math.round(w)), dh = Math.max(1, Math.round(h));
    if (dx > this.cv.width || dy > this.cv.height || dx + dw < 0 || dy + dh < 0) return;
    ctx.globalAlpha = opts.alpha ?? 1;
    if (opts.blend) ctx.globalCompositeOperation = opts.blend;
    const src = opts.tint ? this.tinted(opts.key, f, opts.tint) : f.img;
    const sx0 = opts.tint ? 0 : f.x, sy0 = opts.tint ? 0 : f.y;
    if (flip) {
      ctx.save(); ctx.translate(dx + dw, dy); ctx.scale(-1, 1);
      ctx.drawImage(src, sx0, sy0, f.w, f.h, 0, 0, dw, dh); ctx.restore();
    } else ctx.drawImage(src, sx0, sy0, f.w, f.h, dx, dy, dw, dh);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  }

  drawPanorama(st) {
    const c = this.cam, A = this.A;
    const F = c.F, kScale = F / 280;
    // sun
    const sunF = A.env('sun');
    let da = angDiff(WORLD.sun.az, c.yaw);
    if (Math.abs(da) < 1.3) this.blit(sunF, this.VW / 2 + Math.tan(da) * F, this.hy - Math.tan(WORLD.sun.el) * F, kScale * 1.0, { blend: 'lighter', alpha: st.sunGlow ?? 1 });
    for (const cl of CLOUDS) {
      const az = cl.az + st.t * cl.v;
      da = angDiff(az, c.yaw);
      if (Math.abs(da) > 1.35) continue;
      this.blit(A.env(cl.spr), this.VW / 2 + Math.tan(da) * F, this.hy - Math.tan(cl.el) * F, kScale * cl.s, { alpha: 0.95 });
    }
    for (const p of PANORAMA) {
      da = angDiff(p.az, c.yaw);
      if (Math.abs(da) > 1.35) continue;
      this.blit(A.env(p.spr), this.VW / 2 + Math.tan(da) * F, this.hy + 0.5, kScale * p.s);
    }
  }

  // world billboards ------------------------------------------------------
  drawBillboards(st, list) {
    const items = [];
    const c = this.cam, A = this.A;
    const fogD = st.fog || 4200;
    const hazeCss = st.hazeCss || '#bee2ec';
    for (const o of list) {
      const p = this.project(o.x, o.y || 0, o.z);
      if (!p || p.depth < 6) continue;
      if (p.depth > 12000) continue;
      const m = 260 * p.k * (o.s || 1);
      if (p.sx < -m || p.sx > this.VW + m) continue;
      items.push({ o, p });
    }
    items.sort((a, b) => b.p.depth - a.p.depth);
    for (const { o, p } of items) {
      const k = p.k * (o.s || 1);
      let alpha = 1;
      if (p.depth < 70 && !o.noNearFade) alpha = clamp((p.depth - 18) / 52);
      if (alpha <= 0) continue;
      let fog = p.depth / (p.depth + fogD); fog = fog * fog * (st.fogAmt ?? 1);
      if (o.draw) { o.draw(this, p, k, alpha, fog); continue; }
      let key = o.spr;
      if (o.anim) key = o.spr + '_' + (Math.floor(st.t * o.anim.fps + o.anim.off) % o.anim.frames);
      const f = A.env(key);
      if (!f) continue;
      this.blit(f, p.sx, p.sy, k, { flip: o.flip, alpha });
      if (o.glow && st.runeGlow > 0) this.blit(A.env(o.glow), p.sx, p.sy, k, { flip: o.flip, alpha: alpha * st.runeGlow * (0.6 + 0.4 * Math.sin(st.t * 3 + o.x)), blend: 'lighter' });
      // portal light tint on nearby objects
      if (st.portalI > 0.02 && o.kind !== 'mountain') {
        const dd = Math.hypot(o.x - WORLD.portal.x, o.z - WORLD.portal.z);
        const pk = clamp(1 - dd / 340) ** 2 * st.portalI * 0.55;
        if (pk > 0.02) this.blit(f, p.sx, p.sy, k, { flip: o.flip, alpha: alpha * pk, tint: '#5ec8ff', key, blend: 'source-over' });
      }
      if (fog > 0.03) this.blit(f, p.sx, p.sy, k, { flip: o.flip, alpha: alpha * Math.min(0.92, fog), tint: hazeCss, key });
    }
  }

  // post effects ------------------------------------------------------------
  grade(st) {
    const ctx = this.ctx, W = this.cv.width, Hh = this.cv.height;
    if (st.mul) {
      ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = st.mul; ctx.globalAlpha = st.mulAmt ?? 1;
      ctx.fillRect(0, 0, W, Hh);
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    if (st.add) {
      ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = st.add; ctx.globalAlpha = st.addAmt ?? 1;
      ctx.fillRect(0, 0, W, Hh);
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    // vignette
    const v = st.vignette ?? 0.45;
    if (v > 0) {
      if (!this.vig || this.vig.w !== W || this.vig.h !== Hh) {
        const g = ctx.createRadialGradient(W / 2, Hh * 0.48, Math.min(W, Hh) * 0.25, W / 2, Hh * 0.5, Math.hypot(W, Hh) * 0.62);
        g.addColorStop(0, 'rgba(8,10,24,0)'); g.addColorStop(1, 'rgba(8,10,24,1)');
        this.vig = { w: W, h: Hh, g };
      }
      ctx.globalAlpha = v; ctx.fillStyle = this.vig.g; ctx.fillRect(0, 0, W, Hh); ctx.globalAlpha = 1;
    }
  }
  // dithered fade: amount 0 (clear) .. 1 (fully colour)
  ditherFill(amount, color = '#05060c') {
    if (amount <= 0) return;
    const ctx = this.ctx;
    if (amount >= 1) { ctx.fillStyle = color; ctx.fillRect(0, 0, this.cv.width, this.cv.height); return; }
    const key = Math.round(amount * 16);
    if (!this.dith) this.dith = {};
    const ck = key + color;
    if (!this.dith[ck]) {
      const cv = document.createElement('canvas'); cv.width = 4; cv.height = 4;
      const x = cv.getContext('2d'); x.fillStyle = color;
      for (let i = 0; i < 16; i++) if (BAYER4[i] < key / 16) x.fillRect(i % 4, (i / 4) | 0, 1, 1);
      this.dith[ck] = cv;
    }
    // draw the 4x4 pattern scaled to virtual pixels
    const s = this.s, cv = this.dith[ck];
    if (!this.dithBig || this.dithBig.key !== ck + s) {
      const big = document.createElement('canvas');
      const cell = Math.max(1, Math.round(s));
      big.width = 4 * cell; big.height = 4 * cell;
      const bx = big.getContext('2d'); bx.imageSmoothingEnabled = false; bx.drawImage(cv, 0, 0, big.width, big.height);
      this.dithBig = { key: ck + s, pat: ctx.createPattern(big, 'repeat') };
    }
    ctx.fillStyle = this.dithBig.pat; ctx.fillRect(0, 0, this.cv.width, this.cv.height);
  }
}
