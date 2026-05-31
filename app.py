from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from pydantic import BaseModel
from pydub import AudioSegment, effects
import fitz
import subprocess
import shutil
import hashlib
import os
import re
import threading
import uuid
import unicodedata
from collections import Counter, OrderedDict

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _envf:
        for _line in _envf:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

import azure_voice
import kokoro_voice
import auth

auth.init_db()

app = FastAPI()

MODEL_PATH = os.path.abspath("models/en_US-lessac-medium.onnx")
# Resolve piper: explicit PIPER_EXEC env var → `piper` on PATH (pip install
# piper-tts) → the local dev path. Lets the same code run on a server unchanged.
PIPER_EXEC = (os.environ.get("PIPER_EXEC")
              or shutil.which("piper")
              or os.path.expanduser("~/OpenWebTTS/venv/bin/piper"))
MODELS_DIR = os.path.abspath("models")
CACHE_DIR  = os.path.abspath("audio_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

_BIDI_CONTROL_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_NO_SPACE_BEFORE = set("،؛؟!,.:)]}»…٪%")
_NO_SPACE_AFTER = set("([{«")
# Privacy: the render cache holds raw PDF bytes only long enough to rasterize
# page images. Each entry tracks the set of client session-ids (mnfz_sid cookie)
# that uploaded that exact PDF, so /page-image only serves bytes back to the
# session that supplied them — another user can never fetch your pages even if
# they learn the (content-hash) doc_id.
_PDF_RENDER_CACHE: OrderedDict[str, dict] = OrderedDict()  # doc_id -> {"bytes":bytes,"owners":set[str]}
_PDF_RENDER_CACHE_LOCK = threading.Lock()
_MAX_RENDER_CACHE_DOCS = 8
_MIN_RENDER_SCALE = 0.5
_MAX_RENDER_SCALE = 4.5
_SID_COOKIE = "mnfz_sid"
_SID_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


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

def remember_pdf_for_render(doc_id: str, pdf_bytes: bytes, owner: str) -> None:
    with _PDF_RENDER_CACHE_LOCK:
        entry = _PDF_RENDER_CACHE.get(doc_id)
        if entry is None:
            entry = {"bytes": pdf_bytes, "owners": set()}
            _PDF_RENDER_CACHE[doc_id] = entry
        if owner:
            entry["owners"].add(owner)
        _PDF_RENDER_CACHE.move_to_end(doc_id)
        while len(_PDF_RENDER_CACHE) > _MAX_RENDER_CACHE_DOCS:
            _PDF_RENDER_CACHE.popitem(last=False)

def cached_pdf_for_render(doc_id: str, owner: str) -> bytes | None:
    with _PDF_RENDER_CACHE_LOCK:
        entry = _PDF_RENDER_CACHE.get(doc_id)
        if entry is None:
            return None
        # Ownership check: only a session that uploaded this PDF may render it.
        if not owner or owner not in entry["owners"]:
            return None
        _PDF_RENDER_CACHE.move_to_end(doc_id)
        return entry["bytes"]

def _client_sid(request: Request) -> str:
    """Return the caller's existing mnfz_sid cookie, or '' if not set."""
    return request.cookies.get(_SID_COOKIE, "") or ""

def clean_extracted_text(text: str) -> str:
    return _BIDI_CONTROL_RE.sub("", unicodedata.normalize("NFC", text or "")).strip()

def join_extracted_tokens(tokens: list[str]) -> str:
    cleaned = [clean_extracted_text(token) for token in tokens]
    cleaned = [token for token in cleaned if token]
    if not cleaned:
        return ""

    out = cleaned[0]
    for token in cleaned[1:]:
        if token[0] in _NO_SPACE_BEFORE or out[-1] in _NO_SPACE_AFTER:
            out += token
        else:
            out += " " + token
    return out

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


# ── Auth Routes ───────────────────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    credential: str
    nonce: str = ""

@app.post("/auth/google")
async def google_auth(req: GoogleAuthRequest):
    payload = auth.verify_google_token(req.credential)
    if payload is None:
        return JSONResponse({"error": "Invalid Google token"}, status_code=401)

    # Verify nonce if provided
    if req.nonce and payload.get("nonce") != req.nonce:
        return JSONResponse({"error": "Nonce mismatch"}, status_code=401)

    user = auth.get_or_create_user(payload)
    token = auth.create_app_token(user)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "picture": user.get("picture", ""),
        },
    }

def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    payload = auth.verify_app_token(authorization[7:])
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

@app.get("/auth/me")
async def get_me(authorization: str | None = Header(None)):
    user = _require_user(authorization)
    return {"user": user}

@app.get("/user/docs")
async def list_user_docs(authorization: str | None = Header(None)):
    user = _require_user(authorization)
    docs = auth.get_user_docs(int(user["sub"]))
    return {"docs": docs}

class SaveDocRequest(BaseModel):
    doc_id: str
    filename: str
    page_count: int = 0
    file_size: int = 0

@app.post("/user/docs")
async def save_user_doc(req: SaveDocRequest, authorization: str | None = Header(None)):
    user = _require_user(authorization)
    auth.save_user_doc(int(user["sub"]), req.doc_id, req.filename,
                       req.page_count, req.file_size)
    return {"ok": True}

class SaveProgressRequest(BaseModel):
    doc_id: str
    current_page: int
    scroll_offset: float = 0

@app.post("/user/progress")
async def save_progress(req: SaveProgressRequest, authorization: str | None = Header(None)):
    user = _require_user(authorization)
    auth.save_reading_progress(int(user["sub"]), req.doc_id,
                               req.current_page, req.scroll_offset)
    return {"ok": True}

@app.get("/user/progress/{doc_id}")
async def get_progress(doc_id: str, authorization: str | None = Header(None)):
    user = _require_user(authorization)
    progress = auth.get_reading_progress(int(user["sub"]), doc_id)
    return {"progress": progress}


class SavePreferencesRequest(BaseModel):
    voice: str = ""
    engine: str = "piper"
    theme: str = "light"
    lang: str = "ar"

@app.post("/user/preferences")
async def save_prefs(req: SavePreferencesRequest, authorization: str | None = Header(None)):
    user = _require_user(authorization)
    auth.save_preferences(int(user["sub"]), req.voice, req.engine, req.theme, req.lang)
    return {"ok": True}

@app.get("/user/preferences")
async def get_prefs(authorization: str | None = Header(None)):
    user = _require_user(authorization)
    prefs = auth.get_preferences(int(user["sub"]))
    return {"preferences": prefs}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    html = html.replace("__GOOGLE_CLIENT_ID_PLACEHOLDER__", client_id)
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-store, max-age=0"},
    )

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
    # Kokoro premium voices, if the kokoro package is installed.
    kokoro_status = kokoro_voice.availability()
    if kokoro_status["available"]:
        voices.extend(kokoro_voice.list_voices())
    else:
        voices.append({
            "name": "",
            "engine": "kokoro",
            "label": kokoro_voice.unavailable_label(kokoro_status),
            "disabled": True,
            "placeholder": True,
            "diagnostics": kokoro_status,
        })
    # Azure Arabic neural voices, if credentials are configured.
    voices.extend(azure_voice.list_voices())
    return {"voices": voices, "kokoro": kokoro_status}

@app.post("/extract")
async def extract_pdf(request: Request, response: Response, file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    doc_id = hashlib.sha256(pdf_bytes).hexdigest()
    # Bind this upload to the caller's private session. Mint a session id on
    # first upload; only this session may later render the PDF's page images.
    sid = _client_sid(request)
    if not sid:
        sid = uuid.uuid4().hex
        response.set_cookie(
            _SID_COOKIE, sid,
            max_age=_SID_MAX_AGE, httponly=True, samesite="lax",
            secure=(request.url.scheme == "https"),
        )
    remember_pdf_for_render(doc_id, pdf_bytes, sid)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    pages_raw = []
    for page in doc:
        words_raw = page.get_text("words")
        normalized_words = []
        for idx, w in enumerate(words_raw):
            text = clean_extracted_text(w[4])
            if not text:
                continue
            normalized_words.append({
                "x0": w[0],
                "y0": w[1],
                "x1": w[2],
                "y1": w[3],
                "text": text,
                "block": int(w[5]) if len(w) > 5 else 0,
                "line": int(w[6]) if len(w) > 6 else 0,
                "word": int(w[7]) if len(w) > 7 else idx,
            })
        normalized_words.sort(key=lambda w: (
            w["block"],
            w["line"],
            w["word"],
            round(w["y0"], 3),
            round(w["x0"], 3),
        ))
        pages_raw.append({
            "words": normalized_words,
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
        text = join_extracted_tokens([w["text"] for w in words if not w["skip"]])
        pages.append({"text": text, "words": words,
                      "width": pd["width"], "height": pd["height"]})

    return {"doc_id": doc_id, "total_pages": total_pages, "pages": pages}

@app.get("/page-image/{doc_id}/{page_num}")
def page_image(doc_id: str, page_num: int, request: Request, scale: float = 1.6):
    if not re.fullmatch(r"[0-9a-f]{64}", doc_id or ""):
        raise HTTPException(status_code=404, detail="Unknown PDF")

    # Private rendering: serve page images only to the session that uploaded
    # this PDF (cookie set by /extract). Other users get 404 even with a valid
    # doc_id. <img> requests can't carry the JWT header, so ownership is by cookie.
    sid = _client_sid(request)
    pdf_bytes = cached_pdf_for_render(doc_id, sid)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="PDF render cache expired; reload the PDF")

    try:
        scale = float(scale or 1.6)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid scale")
    scale = max(_MIN_RENDER_SCALE, min(scale, _MAX_RENDER_SCALE))
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_num < 1 or page_num > len(doc):
            raise HTTPException(status_code=404, detail="Page not found")
        page = doc[page_num - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Response(
            content=pix.tobytes("png"),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=600"},
        )
    finally:
        doc.close()

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
        elif engine == "azure":
            # Azure neural TTS bills per character — refuse unless explicitly
            # enabled (AZURE_TTS_ENABLED=1), so it can never be hit by accident.
            if not azure_voice.is_available():
                cleanup_file(tmp)
                return JSONResponse(
                    {"error": "Azure TTS is disabled. Set AZURE_TTS_ENABLED=1 to enable paid Azure voices."},
                    status_code=403,
                )
            azure_voice.synthesize(text, req.voice, tmp)
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
