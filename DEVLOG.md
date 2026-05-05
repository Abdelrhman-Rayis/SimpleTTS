# SimpleTTS — Development Knowledge Base

> **For AI agents:** Read this entire file before touching any code.
> After finishing your session, append a new log entry at the bottom.
> Keep the "Current State" section up to date — it's the handoff summary.

---

## Project Overview

**What it is:** A single-file, self-hosted PDF reader with AI text-to-speech.
**Stack:** Pure HTML/CSS/JS frontend (`index.html`) + a Python backend (assumed to run locally).
**Single source of truth:** `/Users/rayis/SimpleTTS/index.html` — the entire UI lives here.

### Backend API endpoints (assumed, not modified by agents)
| Endpoint | Method | Purpose |
|---|---|---|
| `/extract` | POST (multipart) | Upload PDF → returns `{ pages, total_pages }` |
| `/synthesize` | POST (JSON) | `{ text, voice, engine }` → returns audio blob |
| `/voices` | GET | Returns `{ voices: [{name, label, engine}] }` |

### Supported TTS engines
- **Piper** — fast, default
- **Kokoro** — premium quality, slower, has a one-time warm-up

---

## Architecture (index.html)

### Layout
```
body (flex col, 100vh)
└── .app (flex:1, position:relative)
    ├── .sidebar  ← frosted-glass horizontal bar, position:absolute bottom
    │   ├── .sidebar-brand
    │   ├── .card (Playback)  ← transport + rate-row
    │   ├── .card (Document)  ← file-drop + voice select
    │   ├── .card (Navigation) ← pager
    │   └── .status           ← status pill, margin-left:auto
    └── .viewer (main, overflow:auto)
        ├── .btn-help
        ├── .placeholder
        ├── .toast
        └── .page-wrap × N   (one per PDF page, lazy-rendered)
            ├── canvas.pdf-canvas
            └── .word-layer
                └── .word-box × M
```

### Key JS globals
| Variable | Type | Purpose |
|---|---|---|
| `pdfPages` | array | `[{text, words, width, height}]` from /extract |
| `pdfDoc` | PDFDocumentProxy | pdf.js document |
| `currentPage` | int | Active (playing) page |
| `visiblePage` | int | Page currently scrolled into view |
| `pageDOM` | object | `{[n]: {wrap, canvas, wordLayer, rendered, wordBoxes, speakable, speakMap}}` |
| `isPlaying` | bool | Playback state |
| `wordBoxes` | array | All word spans for current page (full index) |
| `speakable` | array | Non-skip word spans for current page |
| `speakMap` | array | speakIdx → fullIdx mapping |
| `paragraphs` | array | `[{startSpeakIdx, endSpeakIdx, text}]` |
| `sentenceRanges` | array | Sentence boundaries over speakable indices |
| `playStartIdx` | int | Speakable index where current audio chunk begins |
| `playEndIdx` | int | Speakable index where current audio chunk ends |
| `selectedVoice` | object | `{name, engine}` |
| `playbackRate` | float | Current speed (0.75–1.5) |
| `prefetchState` | object/null | Pre-fetched next paragraph blob |

### Key JS functions
| Function | Purpose |
|---|---|
| `loadPDF(file)` | Upload + extract PDF, build page containers |
| `buildPageContainers()` | Create empty page wraps + set up IntersectionObserver |
| `renderPageInto(n)` | Lazy-render canvas + word boxes for page n (idempotent) |
| `setActivePage(n)` | Switch word/sentence/paragraph state to page n |
| `generateAndPlay(page, speakIdx)` | Synthesize paragraph and start playback |
| `prefetchNextPara(page, idx)` | Fire-and-forget pre-fetch of next paragraph |
| `detectSpeechWindow(blob)` | Silence-trim audio: returns `{start, end, internal, speechOnly}` |
| `applyHighlight(speakIdx)` | Highlight current word + sentence band, auto-scroll |
| `updateHighlight()` | Called from rAF loop; maps audio time → speakable index |
| `pokeIdle()` | Reset sidebar fade timer |
| `togglePlayPause()` | Space-bar handler |
| `stopAudio()` | Full stop + state reset |
| `changeRate(delta)` | Adjust speed and sync slider |

---

## Current State
*(Update this section at the end of every session)*

**Last updated:** 2026-05-05  
**Last agent task:** Added voice note-taking feature (🎤 button + 📝 panel in horizontal bar).

### UI: Sidebar / Bottom Bar
- **Position:** `bottom:14px; left:14px; right:14px` — spans full width, floats above viewer
- **Height:** auto (content-driven, ~54px total)
- **Direction:** `flex-direction:row; align-items:center; gap:6px`
- **Padding:** `7px 12px`
- **Background:** frosted glass — `rgba(255,255,255,.42)`, `backdrop-filter:blur(28px) saturate(1.6)`
- **Border radius:** `14px`
- **Section dividers:** vertical `border-left:1px solid rgba(15,23,42,.1)` hairlines
- **Section headings (`.card h2`):** hidden (`display:none`) — no room in horizontal bar
- **Reveal zone (`.sidebar::after`):** sits above the bar (`bottom:100%; height:28px`)

### UI: Auto-idle Fade
- Sidebar fades to `opacity:0.18` after 2.5 s of inactivity (only when PDF loaded)
- Wakes on: mouse within 60 px above bar, hover, keydown, scroll
- JS trigger: `getBoundingClientRect().top` compared to `e.clientY`

### UI: Viewer
- Padding: `24px 24px 90px 24px` (90px bottom clears the floating bar)
- PDF pages rendered lazily via `IntersectionObserver` (600px root margin)
- Active page gets `box-shadow` ring in `--primary` color

### Playback sizes (current)
| Element | Size |
|---|---|
| Play button | 38×38 px, circle |
| Stop button | 30×30 px, circle |
| Nav arrows | 28×28 px |
| Speed slider | 68px fixed width |
| Page input | 38px wide |

### Voice Notes (added 2026-05-05)
- **🎤 button** in bar → starts Web Speech API recording; pulses red; press again to stop
- **📝 button** in bar → toggles notes panel (floats above bar); badge shows count
- On stop, note is committed: `{ id, text, page, context, ts }` — `context` is the TTS-highlighted sentence at the moment recording started
- Keyboard shortcuts: `N` = record, `M` = toggle panel
- `Copy` exports all notes as plain text to clipboard; `Clear` wipes localStorage
- Notes persist in `localStorage` key `simpletts-notes`
- Requires Chrome/Edge/Safari (Web Speech API); shows toast if unsupported
- Notes panel closes when clicking outside it

### Known issues / TODOs
- [ ] `fname` (filename display) can overflow the bar on long filenames — needs `max-width` + `text-overflow:ellipsis`
- [ ] Voice select disappears (`display:none`) when server returns only 1 voice — could show it greyed out instead
- [ ] No dark mode support
- [ ] Mobile/small screen: bar wraps but sections can look crowded

---

## Session Log

### Session 1 — 2026-05-05
**Agent:** Claude (context window ran out, continued in new session)

**Changes made:**

1. **Frosted-glass sidebar**
   - Changed `.sidebar` from solid panel to `rgba(255,255,255,.42)` + `backdrop-filter:blur(28px) saturate(1.6)`
   - Added `border:1px solid rgba(255,255,255,.35)` and multi-layer `box-shadow`

2. **Flattened card sections**
   - Removed background/border from `.card`, sections now separated by hairline `border-top` dividers
   - Section headings styled as small ALL-CAPS labels

3. **Auto-idle fade**
   - Sidebar dims to `opacity:0.18` after 2.5 s of no interaction (only when PDF loaded)
   - `pokeIdle()` called on mousemove (proximity), keydown, scroll, mouseenter/leave
   - `::after` pseudo-element extends hover zone beyond the sidebar edge

4. **Hidden native `<audio>` bar**
   - Added `#player{display:none}` — the custom play/stop/speed controls are sufficient

5. **Converted to horizontal bottom bar** *(this session)*
   - Sidebar repositioned: `bottom:14px; left:14px; right:14px`
   - `flex-direction` changed from `column` → `row`
   - All element sizes reduced (play 56→38px, stop 42→30px, nav arrows 36→28px)
   - Card dividers changed from horizontal `border-top` → vertical `border-left`
   - Section headings hidden (`display:none`)
   - Speed slider given fixed `68px` width instead of `flex:1`
   - Viewer padding changed from `24px 24px 24px 320px` → `24px 24px 90px 24px`
   - Idle proximity detection updated to use bottom-edge Y coordinate

**Files changed:** `/Users/rayis/SimpleTTS/index.html` (CSS + JS only)

---

### Session 2 — 2026-05-05 (continued)
**Agent:** Claude (new context window, continued from session 1 summary)

**Changes made:**

6. **Knowledge base + launch configs** *(this session)*
   - Created `/Users/rayis/SimpleTTS/DEVLOG.md` (this file)
   - Created `/Users/rayis/SimpleTTS/.claude/launch.json` and `/Users/rayis/.claude/launch.json`
   - Detected server: uvicorn runs via `/Users/rayis/OpenWebTTS/venv/bin/uvicorn`, port **8002** (8001 was occupied)
   - Updated Claude memory (`~/.claude/projects/-Users-rayis/memory/MEMORY.md`) to reference this DEVLOG

7. **Voice note-taking feature**
   - Added 🎤 button (record) and 📝 button (view notes) to horizontal bar as a new `.card`
   - Floating `.notes-panel` (position:absolute, bottom:calc(100%+10px)) slides above the bar
   - Uses `window.SpeechRecognition` / `webkitSpeechRecognition` — no backend changes needed
   - Context captured at recording start: TTS-highlighted sentence from `hlSent[]`
   - Notes persist in localStorage (`simpletts-notes`); Copy/Clear controls; badge count on 📝
   - Keyboard: `N` = record, `M` = toggle panel
   - Added N and M to keyboard shortcut help modal table

**Files changed:** `/Users/rayis/SimpleTTS/index.html` (CSS + HTML + JS)

---

*Append new sessions below this line*
