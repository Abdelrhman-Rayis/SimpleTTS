from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from pydub import AudioSegment, effects
import fitz
import subprocess
import hashlib
import os
import uuid
from collections import Counter

import kokoro_voice

app = FastAPI()

MODEL_PATH = os.path.abspath("models/en_US-lessac-medium.onnx")
PIPER_EXEC = os.path.expanduser("~/OpenWebTTS/venv/bin/piper")
MODELS_DIR = os.path.abspath("models")
CACHE_DIR  = os.path.abspath("audio_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class SynthRequest(BaseModel):
    text:   str
    voice:  str = ""
    engine: str = "piper"


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_wav(path: str) -> None:
    audio = AudioSegment.from_file(path, "wav")
    audio = effects.normalize(audio)
    audio = effects.compress_dynamic_range(audio)
    audio.export(path, format="wav")

def cache_key(text: str, voice: str, engine: str) -> str:
    payload = f"{engine}::{voice}::{text}"
    return hashlib.sha256(payload.encode()).hexdigest()

def cached_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.wav")

def cleanup_file(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass

def piper_synth(text: str, voice: str, output_path: str) -> None:
    model_path = MODEL_PATH
    if voice:
        candidate = os.path.join(MODELS_DIR, voice + ".onnx")
        if os.path.isfile(candidate):
            model_path = candidate
    proc = subprocess.Popen(
        [PIPER_EXEC, "--model", model_path, "--output_file", output_path],
        stdin=subprocess.PIPE,
    )
    proc.communicate(input=text.encode("utf-8"))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/voices")
def list_voices():
    voices = []
    # Piper: each .onnx in models/
    try:
        for f in sorted(os.listdir(MODELS_DIR)):
            if f.endswith(".onnx"):
                name = f[:-5]
                voices.append({
                    "name":   name,
                    "engine": "piper",
                    "label":  name.replace("_", " ").replace("-", " · "),
                })
    except Exception:
        pass
    # Kokoro premium voices, if the kokoro package is installed
    if kokoro_voice.is_available():
        voices.extend(kokoro_voice.list_voices())
    return {"voices": voices}

@app.post("/extract")
async def extract_pdf(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    pages_raw = []
    for page in doc:
        words_raw = page.get_text("words")
        pages_raw.append({
            "words": [{"x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3], "text": w[4]}
                      for w in words_raw],
            "width":  page.rect.width,
            "height": page.rect.height,
        })

    skip_keys: set = set()
    if total_pages >= 5:
        zone_counts: Counter = Counter()
        for pd in pages_raw:
            h = pd["height"] or 1
            seen: set = set()
            for w in pd["words"]:
                rel_y = w["y0"] / h
                if rel_y < 0.08 or rel_y > 0.92:
                    zone = "H" if rel_y < 0.08 else "F"
                    key  = (w["text"].strip().lower(), zone)
                    if key not in seen:
                        zone_counts[key] += 1
                        seen.add(key)
        threshold = max(3, 0.6 * total_pages)
        skip_keys = {k for k, v in zone_counts.items() if v >= threshold}

    pages = []
    for pd in pages_raw:
        h = pd["height"] or 1
        words = []
        for w in pd["words"]:
            rel_y = w["y0"] / h
            in_zone = rel_y < 0.08 or rel_y > 0.92
            zone    = "H" if rel_y < 0.08 else "F"
            skip    = in_zone and (w["text"].strip().lower(), zone) in skip_keys
            words.append({**w, "skip": skip})
        text = " ".join(w["text"] for w in words if not w["skip"])
        pages.append({"text": text, "words": words,
                      "width": pd["width"], "height": pd["height"]})

    return {"total_pages": total_pages, "pages": pages}

@app.post("/synthesize")
async def synthesize(req: SynthRequest, bg_tasks: BackgroundTasks):
    text = req.text.strip()
    if not text:
        return JSONResponse({"error": "No text"}, status_code=400)

    engine = (req.engine or "piper").lower()

    # ── Cache check ──────────────────────────────────────────────────────────
    key  = cache_key(text, req.voice, engine)
    dest = cached_path(key)
    if os.path.exists(dest):
        return FileResponse(dest, media_type="audio/wav")

    # ── Synthesize ───────────────────────────────────────────────────────────
    tmp = os.path.join(CACHE_DIR, f"tmp_{uuid.uuid4().hex}.wav")
    try:
        if engine == "kokoro":
            kokoro_voice.synthesize(text, req.voice, tmp)
        else:
            piper_synth(text, req.voice, tmp)
    except Exception as e:
        cleanup_file(tmp)
        return JSONResponse(
            {"error": f"{engine} synthesis failed: {e}"},
            status_code=503,
        )

    normalize_wav(tmp)
    os.replace(tmp, dest)
    return FileResponse(dest, media_type="audio/wav")
