"""
Azure Speech TTS engine — natural Arabic neural voices.

This module uses the Azure Speech REST API directly so the app does not
need an extra SDK dependency. It is enabled only when both
AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are set.
"""
from __future__ import annotations

import html
import os
import urllib.error
import urllib.request

SAMPLE_RATE = 24000

# Curated Arabic neural voices from Azure Speech's official voice list.
ARABIC_VOICES = [
    ("ar-AE-FatimaNeural", "ar-AE", "Fatima · UAE female"),
    ("ar-AE-HamdanNeural", "ar-AE", "Hamdan · UAE male"),
    ("ar-EG-SalmaNeural", "ar-EG", "Salma · Egypt female"),
    ("ar-EG-ShakirNeural", "ar-EG", "Shakir · Egypt male"),
    ("ar-JO-SanaNeural", "ar-JO", "Sana · Jordan female"),
    ("ar-JO-TaimNeural", "ar-JO", "Taim · Jordan male"),
    ("ar-QA-AmalNeural", "ar-QA", "Amal · Qatar female"),
    ("ar-QA-MoazNeural", "ar-QA", "Moaz · Qatar male"),
    ("ar-SA-ZariyahNeural", "ar-SA", "Zariyah · Saudi female"),
    ("ar-SA-HamedNeural", "ar-SA", "Hamed · Saudi male"),
]


def _has_credentials() -> bool:
    return bool(os.getenv("AZURE_SPEECH_KEY") and os.getenv("AZURE_SPEECH_REGION"))


def _enabled() -> bool:
    # Azure neural TTS is billed per character, so it is OFF unless explicitly
    # opted in. Set AZURE_TTS_ENABLED=1 (or true/yes/on) to turn it on.
    return os.getenv("AZURE_TTS_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def is_available() -> bool:
    return _has_credentials() and _enabled()


def list_voices() -> list[dict]:
    if not _has_credentials():
        return [{
            "name": "",
            "engine": "azure",
            "label": "Configure AZURE_SPEECH_KEY + AZURE_SPEECH_REGION",
            "disabled": True,
            "placeholder": True,
        }]
    if not _enabled():
        return [{
            "name": "",
            "engine": "azure",
            "label": "Azure voices off (paid per character) — set AZURE_TTS_ENABLED=1",
            "disabled": True,
            "placeholder": True,
        }]
    return [
        {"name": voice, "engine": "azure", "label": label, "locale": locale}
        for voice, locale, label in ARABIC_VOICES
    ]


def _endpoint() -> str:
    region = os.getenv("AZURE_SPEECH_REGION", "").strip()
    if not region:
        raise RuntimeError("AZURE_SPEECH_REGION is not set")
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"


def _voice_locale(voice: str) -> str:
    for name, locale, _label in ARABIC_VOICES:
        if name == voice:
            return locale
    parts = voice.split("-")
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return "ar-SA"


def synthesize(text: str, voice: str, output_path: str) -> None:
    key = os.getenv("AZURE_SPEECH_KEY", "").strip()
    if not key:
        raise RuntimeError("AZURE_SPEECH_KEY is not set")
    if not voice:
        voice = "ar-SA-ZariyahNeural"

    locale = _voice_locale(voice)
    ssml = (
        f"<speak version='1.0' xml:lang='{html.escape(locale)}'>"
        f"<voice name='{html.escape(voice)}' xml:lang='{html.escape(locale)}'>"
        f"{html.escape(text)}"
        f"</voice></speak>"
    )

    req = urllib.request.Request(
        _endpoint(),
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "SimpleTTS",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            data = res.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore").strip()
        msg = detail or e.reason or f"HTTP {e.code}"
        raise RuntimeError(msg) from e

    with open(output_path, "wb") as f:
        f.write(data)
