# Bad Apple!! Terminal Player 🍎

Flicker-free, audio-synced Bad Apple!! player for your terminal.

## Features

- **3 Rendering Modes:**
  - `halfblock` (Default): 2x vertical resolution using half-block characters (`▀`, `▄`) for crystal-clear silhouettes.
  - `braille`: Ultra high-resolution rendering using Unicode Braille (2x4 matrix) characters.
  - `ascii`: Classic nostalgic ASCII shading (` .:-=+*#%@`).
- **Zero-Setup & Auto-Provisioning:** Clones and runs immediately! Automatically installs missing dependencies (`opencv-python-headless`, `colorama`, `pygame`) and downloads video/audio assets with MD5 checksum verification.
- **Cross-Platform Audio Engine:** Backed by `pygame.mixer` for distortion-free pause/resume and zero-latency seeking, with fallback to native OS drivers on Windows (`winmm.dll` MCI), macOS (`afplay`), and Linux (`ffplay`/`mpv`/`aplay`).
- **Flicker-Free & Ghost-Free Rendering:** Employs Alternate Screen Buffer (`\033[?1049h`), scrollback buffer purging, and dynamic resizing for a pristine, clean display at 30 FPS.
- **Dynamic Sizing & Visual Scrubber:** Automatically senses terminal dimensions, preserves the 4:3 aspect ratio, centers output, and displays an interactive progress bar.

## Controls

| Key | Action |
|-----|--------|
| **Space** | Pause / Resume |
| **M** | Cycle render modes (`halfblock` → `ascii` → `braille`) |
| **Right Arrow (→)** | Seek forward 5 seconds |
| **Left Arrow (←)** | Seek backward 5 seconds |
| **R** | Restart playback |
| **Q / Esc** | Quit |

## Installation & Quick Start

### Option 1: Install via pip (Recommended)

```bash
pip install bad-apple-in-terminal
```

Run it directly from anywhere in your terminal:
```bash
bad-apple
# or
badapple
```

### Option 2: Run from Source (Zero-Setup)

Just clone and run! Required dependencies and media files are automatically prepared on first launch:

```bash
git clone https://github.com/Ohualtex/bad-apple.git
cd bad-apple
python main.py
```

### Options & Flags

```bash
# Start with a specific render mode (halfblock, ascii, braille)
bad-apple --mode braille

# Disable audio
bad-apple --no-audio

# Set specific terminal width/height
bad-apple --width 100 --height 35
```

### macOS Tips

- **Gapless Half-Block Display:**  
  The default macOS Terminal.app adds vertical font leading (line spacing) between lines. To achieve a seamless, OLED-smooth display:
  1. Open **Terminal** → **Settings** (`Cmd + ,`) → **Profiles** → **Text**.
  2. Click **Change...** under Font.
  3. Expand the font window downward if needed, and set the **Line Spacing** slider to **`0.80`**.
  4. Alternatively, press **`M`** to switch to **Braille mode** (which is naturally immune to line spacing), or use modern terminals like [iTerm2](https://iterm2.com/), [Ghostty](https://ghostty.org/), or [Kitty](https://sw.kovidgoyal.net/kitty/).


