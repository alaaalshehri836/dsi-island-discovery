"""
Generate the human-voice narration for DSI Island - Part 1.

Uses Kokoro-82M (Apache-2.0 open-weight neural TTS) through kokoro-onnx.
Model files (download once, ~350 MB):
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

Usage:
  python gen_narration.py --models /path/to/model/dir --out ../assets/audio/narration
Writes <out>/<voice-set>/nNN.mp3 plus narration.json with exact durations.
"""
import argparse, json, os, subprocess, tempfile
import numpy as np, soundfile as sf
from scipy.signal import fftconvolve
from kokoro_onnx import Kokoro

LINES = [
    ("n01", "A new world is waiting..."),
    ("n02", "Every journey begins somewhere."),
    ("n03", "Something is waiting for you..."),
    ("n04", "Some discoveries change everything."),
    ("n05", "The adventure is just beginning."),
    ("n06", "Meet us at DSI. Your next adventure starts here."),
]
# voice sets: (folder, kokoro voice, lang, speed)
VOICES = [
    ("female", "af_heart", "en-us", 0.86),
    ("male", "bm_george", "en-gb", 0.88),
]

def room_ir(sr, seconds=1.1, seed=3):
    rng = np.random.default_rng(seed)
    n = int(sr * seconds)
    t = np.arange(n) / sr
    ir = rng.standard_normal(n) * np.exp(-t * 6.5)
    # soften highs of the tail
    k = np.ones(6) / 6
    ir = np.convolve(ir, k, mode="same")
    ir[0] = 0
    return ir / np.sqrt(np.sum(ir ** 2))

def trim(x, sr, thresh=0.008, pad_start=0.04, pad_end=0.12):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(pad_start * sr)); b = min(len(x), idx[-1] + int(pad_end * sr))
    return x[a:b]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    k = Kokoro(os.path.join(a.models, "kokoro-v1.0.onnx"), os.path.join(a.models, "voices-v1.0.bin"))
    meta = {}
    for folder, voice, lang, speed in VOICES:
        od = os.path.join(a.out, folder); os.makedirs(od, exist_ok=True)
        meta[folder] = {"voice": voice, "lines": {}}
        for key, text in LINES:
            s, sr = k.create(text, voice=voice, speed=speed, lang=lang)
            s = trim(np.asarray(s, dtype=np.float64), sr)
            # subtle, warm "cinematic room": 7% wet short reverb, fade tail
            wet = fftconvolve(s, room_ir(sr))[: len(s) + int(0.5 * sr)]
            dry = np.concatenate([s, np.zeros(len(wet) - len(s))])
            y = dry + 0.07 * wet / (np.max(np.abs(wet)) + 1e-9) * np.max(np.abs(s))
            fade = int(0.25 * sr); y[-fade:] *= np.linspace(1, 0, fade)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                sf.write(tf.name, y.astype(np.float32), sr)
                mp3 = os.path.join(od, key + ".mp3")
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tf.name,
                                "-af", "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,loudnorm=I=-16:TP=-1.5:LRA=7",
                                "-ar", "44100", "-ac", "1", "-b:a", "128k", mp3], check=True)
                os.unlink(tf.name)
            speech = len(s) / sr
            meta[folder]["lines"][key] = {"text": text, "speech": round(speech, 3)}
            print(folder, key, round(speech, 2), "s")
    with open(os.path.join(a.out, "narration.json"), "w") as f:
        json.dump(meta, f, indent=2)

if __name__ == "__main__":
    main()
