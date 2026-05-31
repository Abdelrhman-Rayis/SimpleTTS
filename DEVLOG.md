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
- **Azure Speech** — optional cloud-backed Arabic neural voices
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
**Last agent task:** Added optional Azure Speech Arabic voices for more natural pronunciation.

### UI: Sidebar / Bottom Bar
- **Position:** `bottom:14px; left:14px; right:14px` — spans full width, floats above viewer
- **Height:** auto (content-driven, ~66px total on desktop)
- **Direction:** `flex-direction:row; align-items:center; gap:7px`
- **Padding:** `8px 12px`
- **Background:** paper/glass rail — warm translucent gradient with `backdrop-filter:blur(26px) saturate(1.25)`
- **Border radius:** `12px`
- **Section dividers:** vertical `border-left:1px solid rgba(50,61,68,.14)` hairlines
- **Section headings (`.card h2`):** hidden (`display:none`) — no room in horizontal bar
- **Reveal zone (`.sidebar::after`):** sits above the bar (`bottom:100%; height:28px`)

### UI: Auto-idle Fade
- Sidebar fades to `opacity:0.18` after 2.5 s of inactivity (only when PDF loaded)
- Wakes on: mouse within 60 px above bar, hover, keydown, scroll
- JS trigger: `getBoundingClientRect().top` compared to `e.clientY`

### UI: Viewer
- Padding: `34px 24px 112px 24px` (112px bottom clears the floating bar)
- Background: cool desk/paper gradient with subtle grain overlay
- PDF pages have off-white paper backgrounds, stronger layered shadows, faint page-edge overlays, and an ink-colored active ring
- PDF pages rendered lazily via `IntersectionObserver` (600px root margin)
- Active page gets a slight lift plus `box-shadow` ring in `--primary` color

### Access & Focus Tools (added 2026-05-05)
- **Aa button** floats below the mic button and opens `#accessPanel`
- Preferences persist in `localStorage` key `simpletts-access`
- Tools: high contrast, ADHD focus mode, reading guide, reduce motion, readable extracted text
- Keyboard shortcuts: `A` = access panel, `G` = reading guide, `F` = ADHD focus mode
- High contrast sharpens controls, page active ring, and word/sentence highlights
- ADHD focus mode dims inactive pages and removes visual grain/noise
- Reading guide follows pointer movement and jumps to the currently spoken word line during playback
- Readable text pane exposes extracted paragraph text as real DOM buttons, useful for screen readers and distraction-reduced reading
- Readable paragraphs can be clicked to start TTS from that paragraph

### Azure Arabic Voices (added 2026-05-05)
- Azure voices are exposed only when `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are set
- Added a REST-based Azure Speech backend in `azure_voice.py` to avoid an extra SDK dependency
- Voice dropdown now shows a curated Arabic neural set from Azure Speech, grouped under `Azure Speech (Arabic neural)`
- Synthesized audio uses the Azure SSML endpoint with `riff-24khz-16bit-mono-pcm` output so it flows through the existing highlight pipeline
- When credentials are missing, `/voices` now returns a disabled Azure placeholder so the UI explains how to enable it

### Playback sizes (current)
| Element | Size |
|---|---|
| Play button | 38×38 px, circle |
| Stop button | 30×30 px, circle |
| Nav arrows | 28×28 px |
| Speed slider | 74px fixed width |
| Page input | 40px wide |

### Voice Notes (added 2026-05-05)
- **🎤 button** floats in the viewer below the help button → starts Web Speech API recording; pulses red; press again to stop
- Same **🎤 button** opens/closes the floating notes panel when notes already exist; badge shows count
- On stop, note is committed: `{ id, text, page, context, speakIdx, ts }` — `context` is the TTS-highlighted sentence at the moment recording started; `speakIdx` is saved when available
- Clicking a note pauses playback, opens the recorded page, and highlights the saved context text; older notes without `speakIdx` fall back to context-text matching
- Keyboard shortcuts: `N` = record, `M` = toggle panel
- `Copy` exports all notes as plain text to clipboard; `Clear` wipes localStorage
- Notes persist in `localStorage` key `simpletts-notes`
- Requires Chrome/Edge/Safari (Web Speech API); shows toast if unsupported
- Notes panel floats top-right and closes when clicking outside it

### Known issues / TODOs
- [ ] Voice select disappears (`display:none`) when server returns only 1 voice — could show it greyed out instead
- [ ] No dark mode support
- [ ] Mobile/small screen: wrapping is improved but still needs real-device testing with long filenames and many voices
- [ ] Access & Focus tools need real assistive-technology testing with VoiceOver/NVDA and Arabic PDFs

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

### Session 3 — 2026-05-05
**Agent:** Codex

**Changes made:**

8. **Modern paper-like interface refresh**
   - Reworked the color system from the previous purple/slate palette to ink teal, warm paper, and cool desk tones
   - Replaced the glass-heavy bottom bar with a warmer paper/glass control rail
   - Added more dimensional PDF page styling: off-white page surface, layered shadows, subtle paper-edge overlays, and a clearer active-page ring
   - Restyled buttons, selects, file picker, status pill, notes panel, help modal, and empty state to match the paper direction
   - Replaced the emoji brand/empty-state marks with cleaner text marks (`ST`, `PDF`)
   - Increased filename truncation width and made `.fname` ellipsis-safe
   - Improved small-screen behavior by letting the bottom rail wrap, hiding the brand on narrow layouts, and giving the viewer extra bottom clearance

**Files changed:** `/Users/rayis/SimpleTTS/index.html` (CSS + small HTML label changes)

---

### Session 4 — 2026-05-05
**Agent:** Codex

**Changes made:**

9. **Clickable voice notes**
   - Note cards now act as keyboard-accessible buttons
   - Clicking a note pauses playback, renders/opens the page where it was taken, and highlights the saved context text
   - New notes store `speakIdx` when available, so they can fall back to the exact sentence/word position if text matching fails
   - Existing notes remain compatible through context-text matching on the saved page
   - Page switches now clear old highlight classes before activating the new page

**Files changed:** `/Users/rayis/SimpleTTS/index.html` (CSS + JS)

---

### Session 5 — 2026-05-05
**Agent:** Codex

**Context used:**
- Mada Innovation Award site: emphasizes accessible ICT/assistive technology, Arabic inclusive solutions, AI-based innovation, measurable impact, and a 2026 application window from 10 March to 30 May.
- Local Downloads PDF: `تقرير استراتيجي لترشيح جائزة مدى للابتكار 2026 (1) (1).pdf`, which frames the strongest positioning around Arabic-first accessibility, WCAG/WAI-ARIA, explainability, assistive technology, keyboard access, RTL support, and usable Arabic guidance rather than cosmetic overlays.

**Changes made:**

10. **Access & Focus tools**
   - Added top-right `Aa` accessibility button and floating `#accessPanel`
   - Added persisted preferences in `localStorage` (`simpletts-access`)
   - Added high contrast mode, ADHD focus mode, reading guide, reduced motion, and readable extracted text mode
   - Added real DOM extracted-text pane with paragraph buttons that start TTS from the selected paragraph
   - Added keyboard shortcuts: `A` access panel, `G` reading guide, `F` focus mode
   - Added ARIA improvements for status updates, nav buttons, stop button, note button, access panel, and readable pane
   - Prevented global playback shortcuts from firing while focused on buttons/inputs/selects/textareas

**Files changed:** `/Users/rayis/SimpleTTS/index.html` (CSS + HTML + JS), `/Users/rayis/SimpleTTS/DEVLOG.md`

---

### Session 6 — 2026-05-05
**Agent:** Codex

**Changes made:**

11. **Azure Arabic TTS support**
   - Added `azure_voice.py` with a REST-based Azure Speech integration
   - Exposed a curated Arabic neural voice set from Azure Speech, including `ar-AE`, `ar-EG`, `ar-JO`, `ar-QA`, and `ar-SA`
   - Wired `/voices` and `/synthesize` in `app.py` to use Azure when `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are configured
   - Updated the UI voice grouping and loading heuristic in `index.html` so Azure appears as its own engine group and shows a disabled setup hint when unconfigured
   - Documented the Azure setup in `README.md`

**Files changed:** `/Users/rayis/SimpleTTS/azure_voice.py`, `/Users/rayis/SimpleTTS/app.py`, `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/README.md`, `/Users/rayis/SimpleTTS/DEVLOG.md`

*Append new sessions below this line*

### Session 7 — 2026-05-25
**Agent:** Claude

**Problem investigated:**
Visible PDF page text was malformed (e.g. `T h e G eo Io T O n to logy`) on the user's in-app browser. PyMuPDF and Chromium PDF.js both render `Chapter_3_Draft (2).pdf` cleanly, so the bug is PDF.js's Type1/Latin-Modern canvas rendering in WebKit/WKWebView/in-app browsers. A previous session added a server PNG fallback (`/page-image/{doc_id}/{page_num}`) plus a `shouldUseServerPageImages()` UA sniff, but the user's browser was not matching it.

**Changes made (`index.html` only):**

12. **Robust render-mode selector**
    - Replaced `shouldUseServerPageImages()` with `pickRenderMode()`, returning `{mode, source}`.
    - Order of precedence: `?render=image|canvas` URL param → `localStorage['simpletts-render-mode']` → auto-detect.
    - Auto-detect is now *whitelist-based* (image is the default): only desktop Chrome / Firefox / Edge keep `canvas`; Safari, iOS, iPadOS desktop-mode, WKWebView/pywebview, and any in-app browser get `image`.
    - Exposed `window.simplettsSetRenderMode('image'|'canvas')`, `simplettsClearRenderMode()`, and `simplettsRenderInfo()` for quick toggling/inspection from devtools.
    - Sets `document.documentElement.dataset.renderMode` for CSS hooks.

13. **CSS safety nets**
    - Added `html[data-render-mode="image"] .pdf-canvas{display:none!important}` and the mirrored `canvas`→`.pdf-page-image` rule, so a stale element from any other code path can never overpaint the active surface.
    - Hardened `.word-box`: `text-indent:-9999px` plus `.word-box *` enforcement of `font-size:0`, transparent color — guarantees no overlay text glyph ever paints regardless of cached CSS.

14. **Diagnostic badge (opt-in)**
    - Enable with `?diag=1` or `localStorage['simpletts-diag']='1'`. Renders a small top-right pill showing `mode`, `source`, `surface`, `docId`, platform/touch, and full UA.
    - Click to refresh, double-click to flip `image`↔`canvas` (persists to localStorage and reloads).
    - `loadPDF` now calls `updateDiagnosticBadge()` after `serverPdfDocId` is set, so the badge reflects live state.

**Verification:**
- `curl http://127.0.0.1:8001/` returns `Cache-Control: no-store` and the new HTML (152KB, contains `RENDER_MODE`, `data-render-mode`, `pdf-page-image`).
- `POST /extract` with `Chapter_3_Draft (2).pdf` → `doc_id` and 32 pages returned.
- `GET /page-image/<doc_id>/6?scale=1.6` → clean 980×1268 PNG (verified by image read — `Chapter 3 / The GeoIoT Ontology: A Semantic Foundation for Geospatial Knowledge Systems` renders without the Type1 glyph-spacing bug).
- `/voices` includes Piper + Kokoro voices (server is running on `/Users/rayis/OpenWebTTS/venv` Python 3.11).

**Server status:** uvicorn PID 23049 still running on port 8001 with the Kokoro-capable env. No restart required — `/` reads `index.html` per request, so edits are live immediately.

**Quick recipes for the user:**
- Force PNG mode anywhere: open `http://127.0.0.1:8001/?render=image`.
- Persist the choice: in devtools console, `simplettsSetRenderMode('image')`.
- Inspect what mode is active: `simplettsRenderInfo()` in console, or open with `?diag=1`.
- Reset to auto-detection: `simplettsClearRenderMode()`.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

### Session 8 — 2026-05-25
**Agent:** Claude

**Changes made:**

15. **Thmanyah-inspired visual refresh + dark mode**
   - Tokenized every previously hardcoded surface color (hero, cards, search, mini-buttons, modal, panels, notes, readable pane, doc cards, body gradient) into CSS variables on `:root`.
   - Added a `:root[data-theme="dark"]` token set: deep cool charcoal background, warm cream text (`#ece6dc`), elevated card surfaces (`#16191f`), brighter teal primary (`#5ab6c4`), warmer accent orange (`#ff7037`). PDF page surface stays light because that's content, not chrome.
   - Light/dark switch: auto-detects `prefers-color-scheme` on first load, persists manual choice in `localStorage['simpletts-theme']`, and tracks system theme changes when the user hasn't picked manually.
   - New round theme-toggle button (☾/☀) in the library topbar with sun/moon swap on `[data-theme]` flip; rotates on hover.
   - Polished interaction rhythm: cards now lift on hover (`translateY(-3px)` + deeper shadow + accent border), spotlight and doc cover images zoom slightly (`scale(1.04)`), hero copy gets a soft radial accent glow, search field highlights its border on focus, CTAs gained accent-tinted shadows.
   - Refined hero typography (slightly larger clamp range, negative letter-spacing, 14ch max-width) and section headings.
   - Sidebar / panels (`access-panel`, `notes-float`, `readable-pane`) and modal switched to tokenized `--panel-bg` / `--modal-bg` / `--border` so dark mode reads correctly.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

### Session 9 — 2026-05-25
**Agent:** Claude

**Changes made:**

16. **Polish pass — tighter type scale, high-contrast 2.5D player**
   - Tightened the type scale across the home/library surfaces: `section-heading h2` is now `clamp(1.42rem,1.9vw,1.72rem)` (was 2.05rem), `doc-title` 1.16rem (was 1.32rem), `hero-spotlight-copy h3` 1.32rem (was 1.55rem), `hero-stat strong` .88rem (was .96rem), `mix-card strong` 1.22rem (was 1.45rem). `home-toplink-stack strong`, `.home-nav button`, and `.filter-chip` also shrunk to fit the new scale. Most headings picked up `letter-spacing:-.005…-.008em` for crisper compaction.
   - Reworked the player (`.sidebar`) from a translucent glass strip into a solid warm-cream gradient backplate (`--player-bg-a` → `--player-bg-b`) with a much stronger drop shadow (`0 26px 60px rgba(31,42,50,.22)`) and a top inner highlight. In dark mode the bar lifts to a deep slate (`#1d2128` → `#14171c`) with a high-opacity black drop shadow so it visibly floats above the page.
   - Added a layered set of new CSS tokens for the player surface and control bevels: `--player-bg-a/b`, `--player-border`, `--player-shadow`, `--ctrl-bg-a/b`, `--ctrl-border`, `--ctrl-highlight`, `--ctrl-inner-shadow`, `--ctrl-drop-shadow`, `--ctrl-press-shadow`, `--btn-primary-a/b`, `--btn-ok-a/b`, `--btn-stop-a/b`, plus rate-track tokens. All have light + dark variants on `:root` and `:root[data-theme="dark"]`.
   - Rebuilt every control inside the player with a 2.5D bevel: linear-gradient top→bottom background, 1px top inset highlight (`inset 0 1px 0 var(--ctrl-highlight)`), 1px bottom inset shadow (`inset 0 -1px 0 var(--ctrl-inner-shadow)`), and a layered drop shadow (`0 2px 4px … 0 1px 1px …`). On `:active`, controls press in with `inset 0 2px 4px` and a 1px translate.
   - Coloured pill buttons (`.btn`, `.btn-ok`, `.btn-stop`, `.play-main`) now use a two-stop gradient (`a` highlight → `b` shadow) with `filter:brightness(1.08)` on hover and a deep press-in shadow on active. `.play-main` enlarged from 38px to 42px with a tighter 1.5px inner highlight so it reads as the primary action.
   - Rate slider container, page-number input, status pill, file-drop, and `select.sel` all upgraded with the same bevel formula so the whole player reads as one cohesive set of physical controls.
   - Verified in preview at desktop light, desktop dark, and mobile (375×812). No console errors.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

### Session 10 — 2026-05-25
**Agent:** Claude

**Changes made:**

17. **Button audit — fix dead nav targets and empty-state UX**
   - Root cause of "متابعة doesn't work": `renderContinueShelf` was hiding the entire `#continue-section` (`style.display='none'`) whenever there were 0 in-progress documents. The topbar "متابعة" button used `scrollIntoView` on that section, so clicking it silently scrolled to a hidden element. From the user's perspective, the button looked broken.
   - Fix 1 — always render the section: removed the `display:none` branch in `renderContinueShelf` ([index.html](index.html) ~line 1774). When no items match, the shelf now shows a friendly empty message ("لا توجد قراءات قيد المتابعة. ابدأ تشغيل أي ملف…") so the scroll target is always visible.
   - Fix 2 — differentiated library empty states in `renderRecentGrid` (~line 1823): if `libraryItems.length > 0` but the current filter has no matches, show a "no matches for this filter" message with an inline button to reset to `all`; otherwise (truly empty library) show the original "drop a PDF" message.
   - Fix 3 — dim filter chips with `count === 0` (except the "all" chip) by adding a `.empty` class and `.filter-chip.empty{opacity:.5}` CSS rule. Hover still highlights so the chip stays clickable.
   - Manually walked every `onclick=` handler in the file: all 30+ handlers resolve to defined functions (`window.setLibraryFilter`, `window.openDocFromLibrary`, `setHomeView`, etc.). No other dead targets found.

18. **Render-mode default flipped to image (PNG) for all browsers**
   - Some users were still hitting the Type1/Latin-Modern glyph-spacing bug when opening PDFs in a real browser (the canvas path in PDF.js renders these fonts with broken kerning on WebKit and occasionally on Chromium too).
   - Simplified `detectDefaultRenderMode()` ([index.html](index.html) ~line 1166) to unconditionally return `'image'`. The previous UA-based whitelist was a partial fix; flipping the default makes the universal-safe path the default for everyone.
   - Canvas mode remains available as an explicit opt-in: append `?render=canvas` to the URL, or call `simplettsSetRenderMode('canvas')` in devtools.
   - Server-side rendering uses PyMuPDF (`/page-image/{doc_id}/{page_num}`) which has zero font-rendering edge cases because it produces a PNG.

19. **Mada Innovation Award — Arabic pitch deck**
   - User is applying for the [Mada Innovation Award](https://award.mada.org.qa/) (Qatar, accessibility-focused, 3 categories × 120,000 QR). Submission window Mar 10 – Jun 20, 2026.
   - Captured 7 product screenshots with Playwright headless Chromium at retina pixel ratios (`/Users/rayis/SimpleTTS/capture_screens.py`): `home_light`, `home_dark`, `player_light`, `player_dark`, `mobile_light`, `mobile_dark`, `hero_light`. Output in `/Users/rayis/SimpleTTS/deck_assets/`.
   - Generated a 10-slide Arabic RTL PowerPoint at `/Users/rayis/SimpleTTS/munfath_mada_pitch.pptx` (1.4MB, screenshots embedded). Source: `/Users/rayis/SimpleTTS/build_deck.py` using python-pptx 1.0.2. Palette pulled directly from the product (`#F7EFE2` cream, `#E85D2C` orange, `#245C69` teal, Tajawal font). RTL forced per-paragraph via `p._p.get_or_add_pPr().set('rtl','1')`.
   - Slide order: Title → Problem → Solution (home_light) → How it works (3 steps) → Dark mode (home_dark) → 4 features → 4 audience → Multi-device (mobile_light + hero_light side-by-side) → Roadmap timeline → Closing (dark slide).

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`
**Files added:** `/Users/rayis/SimpleTTS/capture_screens.py`, `/Users/rayis/SimpleTTS/build_deck.py`, `/Users/rayis/SimpleTTS/deck_assets/*.png`, `/Users/rayis/SimpleTTS/munfath_mada_pitch.pptx`

---

### Session 11 — 2026-05-26
**Agent:** Mnfz, coordinating Claude Code and Codex in tmux

**Changes made:**

20. **Premium SimpleTTS welcome page**
   - Reworked the existing `#libraryHome` surface into a clearer Arabic-first welcome page for SimpleTTS / منفذ.
   - Updated the hero copy to explain the core flow plainly: open a PDF, listen with highlighted reading, and resume later from the local library.
   - Added a concise English secondary line for bilingual clarity without making English the default.
   - Added three welcome steps: choose the PDF, listen with focus, and return later.
   - Shifted the welcome page visual language toward Abdelrhman's preferred premium minimalist system: ink-dark `#1a1f2e`, gold `#b8924a`, sharp 4px corners, solid buttons, hairline borders, and no AI-marketing pill/shadow styling on the welcome surface.

21. **Coordination + safety hardening**
   - Managed the other tmux agents in read-only support roles: Claude provided UX checklist guidance; Codex provided verification and breakage-risk checklist guidance.
   - Kept file ownership with Mnfz only to avoid overlapping edits in the already-dirty repository.
   - Added null checks around the welcome/library DOM entry points (`openFileChooser`, `showLibraryHome`, `showReaderView`, `renderLibraryHome`, search listener, and library render targets) to reduce crash risk if the page structure changes later.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`



---

### Session 12 — 2026-05-28
**Agent:** Claude Code (Opus 4.7), single-agent QA pass

**Changes made:**

22. **QA pass: full backend + frontend + persistence + desktop boot sweep**
   - Ran the app on `.venv311` at `http://127.0.0.1:8001` via preview MCP, exercised every previewable surface (welcome, library, reader, notes, access prefs, keyboard shortcuts) plus desktop boot path via `OpenWebTTS/venv`.
   - Backend green: `/`, `/voices` (11 voices with kokoro+piper+azure in OpenWebTTS venv; 10 without kokoro in `.venv311`), `/extract`, `/page-image/{doc}/{n}`, `/synthesize` (1.3 s cold, 32 ms warm cache hit), repeated header/footer skip fires correctly at ≥5 pages, cache key includes engine/voice/text.
   - Library persistence verified: IndexedDB `simpletts-library-v1` with `pdfMeta` + `pdfBlob` stores; full meta schema present.
   - Resume + notes + access prefs + all 9 keyboard shortcuts + filter chips + search all wired correctly.
   - Full report at `/Users/rayis/SimpleTTS/QA_REPORT_2026-05-28.md`.

23. **Bug fix: library blob saved as 0 bytes (P1)**
   - `pdfjsLib.getDocument({ data: ab })` transfers ownership of the ArrayBuffer in PDF.js 3.11.174; the existing `new Blob([ab], { type: "application/pdf" })` at line 2699 was therefore writing an empty Blob into `pdfBlob` IDB store.
   - Every library doc was unreopenable: clicking it post-reload threw "The PDF file is empty, i.e. its size is zero bytes." from PDF.js.
   - Fix is a single-line edit at `index.html:2699` — construct the saved Blob from `file` (the original `File` object is independent of the detached ArrayBuffer) instead of `ab`.
   - Verified: fresh upload now stores `blobBytes === fileSize` with valid `

---

### Session 12 — 2026-05-28
**Agent:** Claude Code (Opus 4.7), single-agent QA pass

**Changes made:**

22. **QA pass: full backend + frontend + persistence + desktop boot sweep**
   - Ran the app on `.venv311` at `http://127.0.0.1:8001` via preview MCP, exercised every previewable surface (welcome, library, reader, notes, access prefs, keyboard shortcuts) plus desktop boot path via `OpenWebTTS/venv`.
   - Backend green: `/`, `/voices` (11 voices with kokoro+piper+azure in OpenWebTTS venv; 10 without kokoro in `.venv311`), `/extract`, `/page-image/{doc}/{n}`, `/synthesize` (1.3 s cold, 32 ms warm cache hit), repeated header/footer skip fires correctly at >=5 pages, cache key includes engine/voice/text.
   - Library persistence verified: IndexedDB `simpletts-library-v1` with `pdfMeta` + `pdfBlob` stores; full meta schema present.
   - Resume + notes + access prefs + all 9 keyboard shortcuts + filter chips + search all wired correctly.
   - Full report at `/Users/rayis/SimpleTTS/QA_REPORT_2026-05-28.md`.

23. **Bug fix: library blob saved as 0 bytes (P1)**
   - `pdfjsLib.getDocument({ data: ab })` transfers ownership of the ArrayBuffer in PDF.js 3.11.174; the existing `new Blob([ab], { type: "application/pdf" })` at line 2699 was therefore writing an empty Blob into `pdfBlob` IDB store.
   - Every library doc was unreopenable: clicking it post-reload threw "The PDF file is empty, i.e. its size is zero bytes." from PDF.js.
   - Fix is a single-line edit at `index.html:2699` — construct the saved Blob from `file` (the original `File` object is independent of the detached ArrayBuffer) instead of `ab`.
   - Verified: fresh upload now stores `blobBytes === fileSize` with valid `%PDF-` header; reopen path loads cleanly.

24. **Bugs documented but not fixed**
   - **B2 (P2):** Welcome page hardcodes light tokens (`#f7f3ea`, `#fffdf9`, `#1a1f2e`, `#b8924a`) at `index.html:651-691`, so dark mode does not propagate to the home view. Reader view is unaffected. Holding the fix until a design call confirms whether Session 11 intended the warm palette as always-light branding.
   - **B4 (P3):** `pageInput` element lacks `max` attribute (`index.html:975`). JS `Math.min` clamps so behavior is correct, only the native spinner is missing the upper bound.
   - **B3 (config):** Kokoro deps absent from `.venv311`. Use OpenWebTTS venv to enable Kokoro, or `pip install kokoro soundfile numpy torch` into `.venv311`.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/.claude/launch.json`, `/Users/rayis/SimpleTTS/.claude/launch.json`, `/Users/rayis/SimpleTTS/DEVLOG.md`
**Files added:** `/Users/rayis/SimpleTTS/QA_REPORT_2026-05-28.md`

---

### Session 13 — 2026-05-28
**Agent:** Claude Code (Opus 4.8), visual-density / declutter pass

**Brief:** The welcome view felt crowded. Tightened hierarchy and breathing room
on a single file (`index.html`) — refining Session 11's premium ink/gold/cream
language, not redesigning it — and fixed the B2 dark-mode regression. Verified in
a live Chrome preview on `:8001` (image render mode, OpenWebTTS-less `.venv311`
not required since the server was already up).

**Changes made (`index.html` only):**

25. **Fixed B2 — welcome dark mode (the headline bug).**
   - The `.viewer.home-mode` block (was `index.html:651-691`) hardcoded light hex
     (`#f7f3ea`, `#fffdf9`, `#1a1f2e`, `#b8924a`, etc.) that *overrode* the existing
     tokens, so dark mode never reached the welcome surface.
   - Added a tokenized welcome palette to `:root` — `--welcome-bg/-surface/-surface-2/
     -ink/-ink-fg/-ink-h/-body/-soft/-gold/-gold-h/-line/-line-2` — with a full
     `:root[data-theme="dark"]` override set (deep charcoal surfaces, cream text,
     brighter gold `#d8b15e`). Rewrote the whole home-mode block to reference these.
   - Verified: at `data-theme="dark"` the welcome bg, hero card, steps, search,
     filter chips, and doc cards all re-skin to dark; the secondary CTA flips to a
     cream button with dark text (computed `#f4ece0` on `#12151b`, legible).

26. **Decluttered the welcome view — one primary CTA, fewer shelves.**
   - Removed the kicker pill (`.hero-live-pill`), the hero stat strip
     (`.hero-summary` / `#librarySummary`, hidden), and the hero spotlight card
     (`#heroSpotlight`, hidden — the recents grid already covers "open the current
     doc"). Hero is now a single column (`.home-hero{grid-template-columns:1fr}`)
     and the h1 clamp shrank from `4.25rem` max to `3.05rem`.
   - Demoted the topbar "افتح PDF" to a quiet **gold outline**, so the hero's
     "ابدأ بملف PDF" is the only solid-gold primary in view at once. The ink-filled
     "افتح آخر قراءة" (`returnToCurrentDoc`) stays as the single secondary.
   - Dropped the redundant third `openFileChooser` trigger ("ابدأ الآن" nav button).
   - English secondary line (`.welcome-en`) now hidden ≤560px (kept on tablet/desktop).
   - Filter chips render only when `libraryItems.length >= 5` (`renderFilterChips`).

27. **Hid the reader rail on the welcome.**
   - The bottom playback bar (`.sidebar`) is reader chrome — every control is
     disabled on the home view, and the floating mic/access buttons were *already*
     hidden in `library-mode` (CSS lines ~472-477). Added
     `.app.library-mode .sidebar{display:none!important}` to complete that pattern.
     `openFileChooser` clicks the input programmatically and drag-drop is bound to
     the viewer, so both still work with the bar hidden. Reduced the now-unneeded
     `.viewer.home-mode` bottom padding from ~150px to 32px (28px on mobile).

28. **Slimmed doc cards to: media + title + 1 progress hint + 1 action.**
   - `renderContinueShelf` / `renderRecentGrid`: removed the overline
     (relative-time • page-count) and the excerpt paragraph, and collapsed the
     dual `فتح` / `متابعة` CTA pair to a single button — `متابعة` when there's saved
     progress, else a quiet `فتح`. The card body click (`openLibraryItem(id,false)`)
     remains the primary open affordance. Tightened `.doc-card-body` and
     `.doc-actions` spacing to suit the shorter card.

**Not changed (already satisfied / out of scope):**
   - Voice picker already groups by engine in `<optgroup>` (verified: 20 voices →
     Piper 2 / Kokoro 8 / Azure 10). Left as-is.
   - Render mode stays `image` (server PNG via PyMuPDF). B1 blob fix intact
     (`new Blob([file], …)` at `index.html:2745`).

**Verification (live Chrome on `:8001`):**
   - 6-screenshot before/after sweep at 1280×800, 768×1024, 375×812 in light + dark.
     Before: welcome stayed light in dark mode, two gold CTAs, kicker/stats/spotlight,
     bar over the home view. After: dark mode propagates everywhere; one gold primary;
     hero + first shelf heading ("أكمل القراءة") above the fold at 1280×800; mobile
     shows hero + both CTAs with no horizontal scroll and no control overlap.
   - All 10 keyboard shortcuts fire: Space, ←/→ (page 3→4 confirmed after scroll
     settle), S, ?, Esc, A, M, G, F, N.
   - Library reopen: `openLibraryItem('doc_…', true)` resumed a 240-page doc at page
     2, switched to reader view, bar reappeared, server `/page-image/` PNGs loaded —
     B1 fix confirmed working.
   - Console clean (only the Chrome-extension message-channel notice and a benign
     play→pause AbortError triggered by the rapid Space-then-S shortcut test).

**Note:** B2 is now resolved; the open TODOs from Session 12 (B4 `pageInput` max
attribute, B3 Kokoro deps in `.venv311`) are untouched.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

## Session 14 — HD page rendering on HiDPI/retina

**Problem:** Server-rendered PDF page images looked pixelated/blurry on retina
displays. Root cause: the server-image render path (`renderPageInto` in
`index.html`) requested `/page-image/.../<n>?scale=1.6` at a fixed `SCALE = 1.6`
and set the CSS box to `width*SCALE`, but never multiplied by
`window.devicePixelRatio`. On a dpr=2 screen the 1.6× bitmap was stretched ~2×
in CSS pixels → soft. (The canvas fallback path already used dpr.)

**Fix:**
- `index.html` (`renderPageInto`, server-image branch): keep CSS size at
  `pdData.{width,height} * SCALE`, but request the bitmap at
  `renderScale = min(SCALE * min(dpr,3), 4.5)`. So a retina screen pulls a
  ~3.2× PNG displayed in a 1.6× CSS box → crisp.
- `app.py`: raised `_MAX_RENDER_SCALE` 3.0 → 4.5 so the higher requested scale
  isn't clamped down. Output stays PNG (lossless), so no JPEG quality loss.
- Thumbnail request (`scale=1.4`) left as-is — it's downscaled to a JPEG anyway.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/app.py`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

## Session 15 — Fix silent audio (autoplay unlock)

**Symptom:** "the sounds don't load" — TTS played no audio.

**Diagnosis (reproduced live on mnfz.tech via Chrome MCP):**
- Server side is fully healthy: `/voices` lists voices, `/synthesize` returns a
  valid 92 KB `audio/wav` (Piper *and* Azure, since `AZURE_TTS_ENABLED=1`), and
  the WAV decodes to 2.1 s mono. Container env confirmed.
- In-page test: a gesture-less `player.play()` throws
  `NotAllowedError: play() failed because the user didn't interact…` and the
  AudioContext is `suspended`. With a real trusted click, the
  `await fetch → play()` pattern works in Chrome — but Safari/iOS is stricter:
  it blocks `<audio>.play()` that runs *after* an `await` (the fetch breaks the
  gesture chain) unless the element was already unlocked within a gesture.
- The three `player.play()` call sites had **no `.catch`**, so the rejection was
  swallowed → silence with the status still showing "playing".

**Fix (`index.html`):**
- Added `unlockAudioPlayback()`: on the first `pointerdown`/`keydown`/`touchstart`
  (capture phase) it resumes the AudioContext and plays a 1-sample silent WAV
  on the shared `<player>` element muted, then pauses — "unlocking" the element
  so later post-await `play()` calls are allowed for the rest of the session.
- Added `safePlay()`: resumes the AudioContext and calls `player.play()` with a
  `.catch`; on `NotAllowedError` it shows "اضغط في أي مكان لتشغيل الصوت" and
  retries on the next gesture, otherwise surfaces the real error in the status.
- Replaced the bare `player.play()` calls in `togglePlayPause` and the
  `startPlayback` closure with `safePlay()`. (`resumePlayback`/`playFromWord`
  route through `generateAndPlay` → `startPlayback`, so they're covered too.)

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

## Session 16 — Avatar photo not showing after login

**Symptom:** After signing in, the profile photo didn't appear, leaving the user
unsure whether they were logged in.

**Cause:** The avatar `<img>` loaded the raw Google photo URL
(`lh3.googleusercontent.com/...`) with no `referrerpolicy`. Google frequently
returns 403 for those profile images when a referrer header is sent, so the
image broke silently and nothing in the bar confirmed the session.

**Fix (`index.html`):**
- Added `referrerpolicy="no-referrer"` to `#userAvatarImg`.
- Added a `#userAvatarInitial` span + `.avatar-initial` style (primary-colored
  circle with the user's first initial).
- New `setAvatarPhoto(url, name)`: shows the photo on load, and on `onerror`
  (or missing URL) falls back to the initial circle — so a logged-in indicator
  always renders. Wired into `updateAuthUI`.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

## Session 16b — Sign-in regression (TDZ crash) — HOTFIX

**Symptom:** After login, neither name nor photo appeared; user couldn't tell
they were signed in.

**Root cause (found via Chrome MCP console on live site):**
```
ReferenceError: Cannot access '_authUser' before initialization
  at currentLibraryOwner (:1777) → renderMixGrid (:2097) → renderLibraryHome
  → showLibraryHome (:1646) → (:3815)
```
Session 14's mix-section change added `currentLibraryOwner()` (which reads
`_authUser`) into `renderMixGrid`. But `renderMixGrid` runs during the initial
`showLibraryHome()` at line ~3815, while `_authUser` was declared with `let` at
~3823 — i.e. in the temporal dead zone. The thrown ReferenceError aborted the
rest of the script, so `checkGoogleRedirect()` (end of script) never ran and
sign-in silently failed. Backend was fine the whole time: `/auth/google`
returns 200 with token + user (verified live).

**Fix (`index.html`):** moved the `_authToken`/`_authUser` declarations up to
before their first use (just above `currentLibraryOwner`), removing the late
`let` block. No other behavior change.

**Files changed:** `/Users/rayis/SimpleTTS/index.html`, `/Users/rayis/SimpleTTS/DEVLOG.md`

---

## Session 17 — Delete documents from the library

**Request:** let the user delete their documents from the library.

**Implementation:**
- `index.html`:
  - New `deleteLibraryItem(id, ev)` — confirms (Arabic prompt), removes the local
    IndexedDB copy via `deleteLibraryEntry` (metadata + PDF blob), best-effort
    `DELETE /user/docs/{id}` when signed in (so it doesn't resync on other
    devices), clears `currentDocMeta` if the open doc was deleted, then
    re-renders. Uses `ev.stopPropagation()` so the click doesn't open the card.
  - Added a "حذف" (delete) button to the card action rows in `renderRecentGrid`,
    `renderContinueShelf`, and the hero spotlight.
  - New `.mini-btn.danger` style (red text, fills red on hover).
- `auth.py`: `delete_user_doc(user_id, doc_id)` — deletes from `user_docs` and
  `reading_progress`.
- `app.py`: `DELETE /user/docs/{doc_id}` route (auth-required).

**Files changed:** `index.html`, `app.py`, `auth.py`, `DEVLOG.md`

---

## Session 18 — Mobile responsiveness (player) + home footer

**Request:** make the design responsive on mobile (elements like the PDF sound
player disappear when opened on a phone), and add a footer on the main page with
the GitHub button in it.

**Cause of the disappearing player:** the `.sidebar` (the frosted-glass player
bar) is `position:absolute; bottom:14px` relative to `.app`. On desktop `.app`
is viewport-height (`body{height:100vh;overflow:hidden}`), so the bar sits at the
bottom of the screen. But the `@media(max-width:900px)` rules switch to
`body{overflow:auto;height:auto}` so the body scrolls and `.app` grows to the
full page height — meaning `bottom:8px` anchored the bar to the bottom of the
*entire page*, not the viewport. It only became visible after scrolling all the
way down, so it looked like it had vanished while reading.

**Fix (`index.html`):**
- `@media(max-width:900px) .sidebar` → `position:fixed` (pins to the viewport so
  the player stays visible while scrolling pages). Also added
  `justify-content:center` and `max-height:42vh;overflow-y:auto` as a safety net
  in case the wrapped bar gets tall. The transport (play/stop) is the first card
  so it always lands on the first visible row.
- Added a `<footer class="home-footer">` inside `.library-home`, after
  `#mixSection`: brand block (منفذ + tagline) on one side, the GitHub button on
  the other, plus a centered copyright line. New `.home-footer*` styles; stacks
  to a column at `max-width:560px`.
- **Moved** the GitHub button out of `.home-topbar` into the footer (per the
  request — "put the github button too there"). Removed the now-orphaned
  `.github-btn{order:6}` rule from the 900px media query.

**Verified:** served `index.html` locally, loaded in Chrome at a phone-width
window. Footer renders correctly in RTL (brand right, GitHub left, copyright
centered); topbar is clean with no GitHub button; no layout breakage. The
`mixSection` stays hidden when logged out (Session 15 behavior, unchanged). The
sidebar `position:fixed` fix is CSS-only and not testable on the home page (the
bar is hidden in home-mode and needs the backend for reading mode), but the
reasoning is verified against the layout.

**Files changed:** `index.html`, `DEVLOG.md`
