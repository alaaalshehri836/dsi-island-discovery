# DSI Island — Part 1: *The Discovery*

**Live:** https://dsi-island-discovery.vercel.app · **Repo:** https://github.com/alaaalshehri836/dsi-island-discovery

An interactive, fully real-time pixel-art cinematic website (no video files) for the DSI university booth.
An explorer reaches a mysterious island and discovers a glowing DSI portal. About 25 s, narrated, scored,
built for vertical 9:16 screens and responsive to any aspect ratio.

## Run locally
The site is static (vanilla ES modules, no build step, no dependencies). It must be served over HTTP
because modules and audio are fetched:

```bash
cd dsi-island
python3 -m http.server 8080
```
Then open http://localhost:8080. Click **START ADVENTURE**. That click also unlocks audio.

Useful URLs:
| URL | What |
|---|---|
| `index.html` | the experience |
| `index.html?voice=male` | alternative narrator (British male voice) |
| `index.html?booth=HALL%20B%20·%20BOOTH%2012&date=12%20MAY%202027&info=...` | override event details without editing code |
| `index.html?t=14.8` | freeze any moment of the film (for review/screenshots) |
| `index.html?frame=final` | the clean final frame for Part 2 (see `docs/PART2_HANDOFF.md`) |

## Configure the event details
Edit `js/config.js`:
```js
export const EVENT = { booth: '[BOOTH LOCATION]', date: '[EVENT DATE]', info: '[MORE EVENT INFO]' };
export const NARRATOR = 'female';   // or 'male'
```
Empty strings hide a line. The placeholders are deliberately left unfilled so that no event details are invented.

## Deploy
This repo is connected to Vercel: every push to `main` redeploys https://dsi-island-discovery.vercel.app automatically.
Vercel settings: framework **Other**, no build command, output directory `.` (see `vercel.json`), no environment variables.

Upload the whole folder, minus `tools/` if you like, to any static host: GitHub Pages, Netlify, Vercel,
S3 or a university web server. No server code or environment variables are needed. Total payload is about 2.6 MB.
For a kiosk at the booth, open it fullscreen (F11) in Chrome, or run it on a vertical screen or tablet.

## Story & shot list (film time in seconds)
| Scene | Time | Shots | Narration / caption |
|---|---|---|---|
| 01 Game start / world revealed | 0–3.6 | CRT power-on on black → dithered fade into a high wide establishing shot that tilts down from the sky to the island; a tiny boat on the sea | "A new world is waiting…" |
| 02 Arrival | 3.6–7.65 | wide low shot behind the boat → side-view tracking shot; boat beaches, the explorer jumps out, walks (footprints in the sand), stops and looks around | "Every journey begins somewhere." |
| 03 Exploration | 7.65–13.0 | side tracking past palms → rear-follow along the jungle path (a glowing rune-stone and an old signpost are hints) → crane up for a wide view of the island and sea → close-up: the explorer notices a blue flicker | "Something is waiting for you…" |
| 04 Discovery | 13.0–19.75 | 3/4 shot approaching something in the distance → camera behind the explorer dollies through parting foliage, the portal awakens (glow, runes, particles, light on the ground) → close-up reaction lit blue → over-the-shoulder shot of the portal (the **final frame**) | "Some discoveries change everything." / "The adventure is just beginning." |
| 05 Final announcement | 19.75–26 | final frame holds; DSI logo with shine, MEET US AT DSI!, YOUR NEXT ADVENTURE STARTS HERE., booth/date/info, REPLAY button | "Meet us at DSI. Your next adventure starts here." |

## How it works
* **One world, many cameras.** `js/world.js` defines a single island: coastline, beach, path, plaza, portal,
  and about 1,400 seeded props. Every shot is just a camera inside it, so geography, screen direction and object
  positions stay consistent between cuts.
* **Renderer** (`js/renderer.js`): an SNES-style "Mode 7" ground renders sea, surf, sand, footprints, stone
  plaza and portal light per virtual pixel. It is drawn into a low-res buffer and scaled up crisply. Billboard
  sprites go on top with depth sorting, haze and portal lighting. There is also a parallax panorama (sun,
  clouds, distant islands). The virtual safe frame is 180×320 (9:16); wider or taller screens see more world.
* **Director** (`js/director.js`): the whole film is a pure function of time, covering camera paths,
  explorer track, boat, portal intensity, captions and ambience levels. It runs on the Web Audio clock, so
  picture, narration, music and footsteps stay in sync.
* **Audio** (`js/audio.js`): everything is preloaded, then scheduled sample-accurately on START. Music is
  ducked under the narrator, ambience beds (ocean, wind, jungle, portal hum) are automated per shot, and
  footsteps fire on the walk-cycle contact frames.

## Character consistency
The explorer is **one 3D primitive model** (`tools/sprites/character.py`): hat, teal scarf, cream shirt,
olive vest, belt pouch, canvas backpack with a red bedroll, and boots. Every sprite is rendered from it as
toon-shaded pixel art with outlines: 16 view directions × idle / walk (8) / look-around / shade-eyes /
react / jump, in daylight and portal-lit versions, plus close-up portraits. The website draws all of
these from one sprite sheet, so the character looks identical from every angle and in every shot.
See `assets/sprites/explorer_reference_sheet.png`.

## Project structure
```
index.html, css/style.css
js/  main.js (composition, UI, loop) · director.js (timeline) · renderer.js · world.js · audio.js
     assets.js · pixelfont.js (hand-made 5×7 font) · config.js (event details) · util.js
assets/sprites/  explorer_sheet.png/.json, explorer_portraits.png/.json, explorer_reference_sheet.png,
                 environment_atlas.png/.json (palms, jungle, rocks, boat, portal + energy frames, mountain,
                 clouds, sun, DSI logo...)
assets/audio/narration/{female,male}/n01–n06.mp3 + narration.json (durations)
assets/audio/music/score_part1.mp3
assets/audio/sfx/  ocean, wind, jungle, portal hum loops · footsteps ×4 · boat, splash, landing,
                   portal reveal, startup, text chime, UI click
tools/  gen_narration.py · gen_audio.py · sprites/{sdf.py, character.py, build_character.py,
        environment.py, build_reference.py} · requirements.txt
docs/   PART2_HANDOFF.md · final_frame_*.png · final_frame.json
```

## Regenerating assets (optional)
```bash
pip install -r tools/requirements.txt
cd tools/sprites && python build_character.py ../../assets/sprites && python environment.py ../../assets/sprites && python build_reference.py ../../assets/sprites
cd .. && python gen_audio.py ../assets/audio
python gen_narration.py --models /path/to/kokoro-models --out ../assets/audio/narration
```

## Credits & licensing
* All visuals were generated procedurally for this project: code-defined 3D model → pixel art, plus procedural
  environment art. There are no third-party images.
* Music and sound effects are original, synthesised from scratch in `tools/gen_audio.py`. There are no samples,
  so no licensing issues.
* Narration was generated with **Kokoro-82M** (open-weight neural TTS, Apache-2.0 licence) via `kokoro-onnx`,
  using voices `af_heart` (default) and `bm_george`. No API keys are needed. To swap in another
  voice service (for example ElevenLabs), replace the six files in `assets/audio/narration/<set>/`, keeping
  the names `n01.mp3`–`n06.mp3`, and update the durations in `narration.json`. The timeline adapts automatically.
