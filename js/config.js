// ============================================================================
// EVENT CONFIGURATION — edit these values (or pass them as URL parameters,
// e.g. index.html?booth=Hall%20B%20%C2%B7%20Booth%2012&date=12%20MAY%202027).
// Empty strings hide the line. Text is rendered with the built-in pixel font
// (A–Z, 0–9 and . , ! ? ' - : / & @ # ( ) [ ] ·).
// ============================================================================
export const EVENT = {
  booth: '[BOOTH LOCATION]',
  date: '[EVENT DATE]',
  info: '[MORE EVENT INFO]',
};
// Narration voice set: 'female' (Kokoro af_heart) or 'male' (Kokoro bm_george). URL: ?voice=male
export const NARRATOR = 'female';

export function readConfig() {
  const q = new URLSearchParams(location.search);
  const ev = { ...EVENT };
  for (const k of Object.keys(ev)) if (q.has(k)) ev[k] = q.get(k);
  return { event: ev, voice: q.get('voice') || NARRATOR };
}
