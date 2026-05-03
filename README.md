# SimpleTTS

A lightweight, continuous AI PDF reader that extracts text from large PDFs, synthesizes speech page-by-page using local Piper TTS, and interactively highlights the text inside a native PDF viewer. Built to run entirely locally for privacy and focus.

## Features
- **Local Offline TTS:** Uses [Piper TTS](https://github.com/rhasspy/piper) for fast, natural-sounding offline speech on macOS.
- **Continuous Page Streaming:** Processes and plays PDF pages sequentially without waiting for the entire document to synthesize.
- **Synchronized Highlighting:** Renders the document using Mozilla's PDF.js, tracking audio duration to provide word/line-level highlighting that syncs with speech.
- **High-DPI Support:** Crisp text rendering on Retina displays.

## Setup
1. Create a virtual environment: `python3 -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Install dependencies: `pip install fastapi uvicorn python-multipart PyMuPDF beautifulsoup4 piper-tts`
4. Download a Piper ONNX model (e.g., `en_US-lessac-medium.onnx`) into the `models/` directory.

## Run
```bash
uvicorn app:app --port 8001 --reload
```
Navigate to `http://127.0.0.1:8001` in your browser.

## Credits
This project was inspired by and contains architectural ideas forked from [Gyyyn/OpenWebTTS](https://github.com/Gyyyn/OpenWebTTS). Thank you to the original author for the foundational concepts regarding FastAPI and local TTS integration.
