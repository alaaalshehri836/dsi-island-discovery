// Web Audio engine: everything is scheduled sample-accurately against the
// AudioContext clock, which is also the master clock of the visuals.
import { ambienceAt } from './director.js';

const A = 'assets/audio/';
export const AUDIO_FILES = {
  music: 'music/score_part1.mp3',
  ocean: 'sfx/amb_ocean.mp3', wind: 'sfx/amb_wind.mp3', jungle: 'sfx/amb_jungle.mp3', hum: 'sfx/portal_hum.mp3',
  step0: 'sfx/step_sand_0.mp3', step1: 'sfx/step_sand_1.mp3', step2: 'sfx/step_sand_2.mp3', step3: 'sfx/step_sand_3.mp3',
  boat: 'sfx/boat_land.mp3', splash: 'sfx/splash.mp3', land: 'sfx/land_sand.mp3', reveal: 'sfx/portal_reveal.mp3',
  startup: 'sfx/startup.mp3', chime: 'sfx/text_chime.mp3', click: 'sfx/ui_click.mp3',
};
const LEVEL = { voice: 1.0, music: 0.42, amb: 0.42, sfx: 0.55 };

export class AudioEngine {
  constructor(voiceSet) {
    this.voiceSet = voiceSet; this.buffers = {}; this.raw = {}; this.sources = []; this.muted = false; this.ok = true;
  }
  async preload(lines, onProgress = () => {}) {
    const files = { ...AUDIO_FILES };
    for (const l of lines) files[l.id] = `narration/${this.voiceSet}/${l.id}.mp3`;
    const keys = Object.keys(files); let n = 0;
    await Promise.all(keys.map(async (k) => {
      try { const r = await fetch(A + files[k]); this.raw[k] = await r.arrayBuffer(); } catch (e) { console.warn('audio', k, e); }
      onProgress(++n / keys.length);
    }));
  }
  // must be called from a user gesture
  async unlock() {
    try {
      if (!this.ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        this.ctx = new AC({ latencyHint: 'interactive' });
        this.master = this.ctx.createGain(); this.master.connect(this.ctx.destination);
        this.bus = {};
        for (const b of ['voice', 'music', 'amb', 'sfx']) { const g = this.ctx.createGain(); g.gain.value = LEVEL[b]; g.connect(this.master); this.bus[b] = g; }
      }
      if (this.ctx.state !== 'running') await this.ctx.resume();
      if (!this.decoded) {
        await Promise.all(Object.entries(this.raw).map(async ([k, ab]) => {
          try { this.buffers[k] = await this.ctx.decodeAudioData(ab.slice(0)); } catch (e) { console.warn('decode', k, e); }
        }));
        this.decoded = true;
      }
      this.master.gain.value = this.muted ? 0 : 1;
    } catch (e) { console.warn('audio disabled', e); this.ok = false; }
  }
  play(key, when, { bus = 'sfx', gain = 1, pan = 0, offset = 0, loop = false } = {}) {
    const b = this.buffers[key]; if (!b || !this.ctx) return null;
    const src = this.ctx.createBufferSource(); src.buffer = b; src.loop = loop;
    if (loop) { src.loopStart = 0.04; src.loopEnd = b.duration - 0.04; }
    const g = this.ctx.createGain(); g.gain.value = gain;
    let node = g;
    if (pan && this.ctx.createStereoPanner) { const p = this.ctx.createStereoPanner(); p.pan.value = pan; g.connect(p); node = p; }
    src.connect(g); node.connect(this.bus[bus]);
    const now = this.ctx.currentTime;
    if (when < now) { offset += now - when; when = now; }
    if (!loop && offset >= b.duration) return null;
    src.start(when, loop ? offset % b.duration : offset);
    this.sources.push(src);
    return { src, g };
  }
  // schedule the whole film starting at film time `from`
  start(from, plan) {
    this.stop();
    if (!this.ctx || !this.ok) { this.base = null; return; }
    const c = this.ctx, base = c.currentTime + 0.08 - from;
    this.base = base;
    const at = (t) => base + t;
    // music with ducking under the narrator
    const m = this.play('music', at(0), { bus: 'music', gain: 1 });
    if (m) {
      const g = m.g.gain; g.setValueAtTime(1, Math.max(c.currentTime, at(0)));
      for (const l of plan.lines) {
        if (l.at + l.dur < from) continue;
        g.setTargetAtTime(0.62, Math.max(c.currentTime, at(l.at - 0.1)), 0.08);
        g.setTargetAtTime(1, Math.max(c.currentTime, at(l.at + l.dur)), 0.25);
      }
    }
    // narration
    for (const l of plan.lines) this.play(l.id, at(l.at), { bus: 'voice' });
    // ambience beds with automated levels
    for (const k of ['ocean', 'wind', 'jungle', 'hum']) {
      const s = this.play(k, at(0), { bus: 'amb', gain: 0, loop: true, offset: from });
      if (!s) continue;
      const g = s.g.gain; g.setValueAtTime(ambienceAt(from)[k], c.currentTime);
      for (let t = Math.ceil(from * 4) / 4; t <= 40; t += 0.25) g.linearRampToValueAtTime(ambienceAt(t)[k] * (t > 30 ? 0.6 : 1), at(t));
    }
    // one-shots
    for (const e of plan.sfx) if (e.t >= from - 0.05) this.play(e.key, at(e.t), { bus: 'sfx', gain: e.gain ?? 1, pan: e.pan || 0 });
  }
  stop() { for (const s of this.sources) { try { s.stop(); } catch (e) {} } this.sources = []; }
  clock() { return this.ctx && this.base != null ? this.ctx.currentTime - this.base : null; }
  setMuted(m) {
    this.muted = m;
    if (this.master) this.master.gain.setTargetAtTime(m ? 0 : 1, this.ctx.currentTime, 0.05);
  }
  click() { if (this.ctx) this.play('click', this.ctx.currentTime, { gain: 0.5 }); }
}
