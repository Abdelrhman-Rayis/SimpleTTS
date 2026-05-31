# منفذ (Mnfz) — Arabic-First Accessibility TTS

An Arabic-first, local text-to-speech PDF reader built for accessibility and focus. Reads PDFs aloud with real-time page-level highlighting, supports multiple voice engines, and runs entirely on-device — no cloud required.

Applied to the **Mada Innovation Award** for accessibility technology.

## Screenshots

### Home Page
| Light | Dark |
|---|---|
| ![Home light](screenshots/deck_home_light.png) | ![Home dark](screenshots/deck_home_dark.png) |

### Reader (Player)
| Light | Dark |
|---|---|
| ![Player light](screenshots/player_light.png) | ![Player dark](screenshots/player_dark.png) |

### Mobile
| Light | Dark |
|---|---|
| ![Mobile light](screenshots/mobile_light.png) | ![Mobile dark](screenshots/mobile_dark.png) |

## Features

- **Arabic-First Bilingual UI:** Full RTL support with English toggle — built for Arabic-speaking users first.
- **Local Offline TTS:** Uses [Piper TTS](https://github.com/rhasspy/piper) for fast, natural-sounding offline speech.
- **High-Quality Voices:** Kokoro (8 voices) and optional Azure Speech (10 voices) for more natural pronunciation.
- **Voice Note-Taking:** Record and replay spoken notes directly in the app.
- **Continuous Page Streaming:** Processes and plays PDF pages sequentially without waiting for the entire document.
- **Synchronized Highlighting:** PDF.js rendering with audio-timed word-level highlighting.
- **Library Shelf:** Track reading progress across multiple documents with saved positions.
- **Dark Mode:** Full light/dark theme support with persistent preference.
- **Keyboard Shortcuts:** Space (play/pause), ←/→ (page nav), S (stop), A/M/G/F/N for navigation.
- **Docker Support:** `Dockerfile` included for containerized deployment.
- **High-DPI Support:** Crisp text rendering on Retina displays.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv311
   source .venv311/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Download Piper ONNX models (e.g., `en_US-lessac-medium.onnx`) into `models/`.
4. For Azure voices, set environment variables:
   ```bash
   export AZURE_SPEECH_KEY=your_key
   export AZURE_SPEECH_REGION=eastus
   ```
5. Enable Azure in `.env`:
   ```
   AZURE_TTS_ENABLED=1
   ```

## Run

```bash
cd ~/SimpleTTS
source .venv311/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8001
```

Navigate to `http://localhost:8001` in your browser.

## Docker

```bash
docker build -t mnfz .
docker run -p 8001:8001 mnfz
```

## Voice Engines

| Engine | Voices | Network |
|---|---|---|
| Piper | 2 (English) | Offline |
| Kokoro | 8 (multi-language) | Offline |
| Azure | 10 (incl. Arabic) | Cloud (optional) |

## Project Structure

```
SimpleTTS/
├── app.py              # FastAPI backend + PDF/TTS pipeline
├── index.html           # Single-page frontend (Vanilla JS + PDF.js)
├── azure_voice.py       # Azure TTS integration
├── kokoro_voice.py      # Kokoro TTS integration
├── desktop.py           # Desktop integration
├── build_deck.py        # Pitch deck builder
├── capture_screens.py   # Screenshot capture tool
├── DEVLOG.md            # Development log (28 sessions)
├── screenshots/         # App screenshots
├── deck_assets/         # Pitch deck source images
├── Dockerfile           # Container build
└── requirements.txt     # Python dependencies
```

## Credits

Originally inspired by [Gyyyn/OpenWebTTS](https://github.com/Gyyyn/OpenWebTTS). Rebuilt and significantly extended with Arabic-first UX, multi-engine TTS, voice notes, library system, and Mada Innovation Award application.
