"""
Kokoro TTS engine — premium voice option.

82M-param neural TTS that runs in seconds on CPU. First call downloads
~150 MB into ~/.cache/huggingface/, cached forever after. Pipeline
instances are kept warm in-process per language code so each request
after the first only pays for inference, not model load.

Voice naming convention from the Kokoro project:
    <lang><gender>_<name>
        lang   — a=US English, b=UK English, e=Spanish, f=French, …
        gender — f=female, m=male
"""
from __future__ import annotations

import threading

SAMPLE_RATE = 24000
REQUIRED_IMPORTS = ("kokoro", "soundfile", "numpy", "torch")

# Curated catalog. Add more from the Kokoro voice list as you like.
VOICES = [
    ("a", "af_bella",     "Bella · US female"),
    ("a", "af_sarah",     "Sarah · US female"),
    ("a", "af_nicole",    "Nicole · US female"),
    ("a", "am_adam",      "Adam · US male"),
    ("a", "am_michael",   "Michael · US male"),
    ("b", "bf_emma",      "Emma · UK female"),
    ("b", "bf_isabella",  "Isabella · UK female"),
    ("b", "bm_george",    "George · UK male"),
]

_pipelines: dict = {}        # lang_code -> KPipeline (kept warm)
_load_lock = threading.Lock()


def availability() -> dict:
    missing = []
    errors = []
    for name in REQUIRED_IMPORTS:
        try:
            __import__(name)
        except ModuleNotFoundError as exc:
            missing.append(exc.name or name)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    missing = sorted(set(missing))
    return {
        "available": not missing and not errors,
        "missing": missing,
        "errors": errors,
    }


def is_available() -> bool:
    return availability()["available"]


def unavailable_label(status: dict | None = None) -> str:
    status = status or availability()
    bits = []
    if status.get("missing"):
        bits.append("missing " + ", ".join(status["missing"]))
    if status.get("errors"):
        bits.append("; ".join(status["errors"]))
    reason = "; ".join(bits) or "not available"
    return f"Kokoro unavailable: {reason}"


def list_voices() -> list[dict]:
    return [{"name": vid, "engine": "kokoro", "label": label}
            for _, vid, label in VOICES]


def _pipeline(lang_code: str):
    if lang_code in _pipelines:
        return _pipelines[lang_code]
    with _load_lock:
        if lang_code in _pipelines:
            return _pipelines[lang_code]
        from kokoro import KPipeline
        # CPU is reliable; MPS is faster on Apple Silicon but Kokoro's
        # MPS backend has had stability issues. Stick with CPU for now.
        _pipelines[lang_code] = KPipeline(lang_code=lang_code, device="cpu")
    return _pipelines[lang_code]


def synthesize(text: str, voice: str, output_path: str) -> None:
    """Render `text` to a WAV at `output_path` using the named Kokoro voice."""
    status = availability()
    if not status["available"]:
        raise RuntimeError(unavailable_label(status))

    import numpy as np
    import soundfile as sf

    if not voice:
        voice = "af_bella"
    lang_code = voice[0] if voice and voice[0].isalpha() else "a"

    pipe = _pipeline(lang_code)

    chunks = []
    for _gs, _ps, audio in pipe(text, voice=voice):
        # Kokoro yields one chunk per synthesized sentence; concatenate them all.
        chunks.append(audio.cpu().numpy() if hasattr(audio, "cpu") else audio)

    if not chunks:
        raise RuntimeError("Kokoro produced no audio for the given text")

    sf.write(output_path, np.concatenate(chunks), SAMPLE_RATE)
