from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import fitz  # PyMuPDF
import subprocess
import os
import uuid

app = FastAPI()

MODEL_PATH = os.path.abspath("models/en_US-lessac-medium.onnx")
PIPER_EXEC = os.path.expanduser("~/OpenWebTTS/venv/bin/piper")

class SynthRequest(BaseModel):
    text: str

def cleanup_file(path: str):
    try:
        os.remove(path)
    except:
        pass

@app.get("/")
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/extract")
async def extract_pdf(file: UploadFile = File(...)):
    # Extract per-page word boxes so the frontend can highlight + click
    # the same tokens that get sent to the TTS engine.
    pdf_bytes = await file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages = []
    for page in doc:
        words_raw = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, word_no)
        words = [
            {"x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3], "text": w[4]}
            for w in words_raw
        ]
        text = " ".join(w["text"] for w in words)
        pages.append({
            "text": text,
            "words": words,
            "width": page.rect.width,
            "height": page.rect.height,
        })

    return {"total_pages": len(pages), "pages": pages}

@app.post("/synthesize")
async def synthesize(req: SynthRequest, bg_tasks: BackgroundTasks):
    text = req.text.strip()
    if not text:
        return {"error": "No text"}

    output_wav = f"output_{uuid.uuid4().hex}.wav"
    
    process = subprocess.Popen(
        [PIPER_EXEC, "--model", MODEL_PATH, "--output_file", output_wav],
        stdin=subprocess.PIPE
    )
    process.communicate(input=text.encode("utf-8"))
    
    # Delete the audio file from disk after sending it to the browser
    bg_tasks.add_task(cleanup_file, output_wav)
    
    return FileResponse(output_wav, media_type="audio/wav")
