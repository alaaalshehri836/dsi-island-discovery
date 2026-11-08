// ============================================================================
// CONFIGURATION
// ============================================================================
// Narration voice set: 'female' (Kokoro af_heart) or 'male' (Kokoro bm_george). URL: ?voice=male
export const NARRATOR = 'female';

export function readConfig() {
  const q = new URLSearchParams(location.search);
  return { voice: q.get('voice') || NARRATOR };
}
