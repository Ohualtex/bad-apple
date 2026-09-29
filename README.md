# Bad Apple!! Terminal Player 🍎

Flicker-free, audio-synced Bad Apple!! player for your terminal.

## Features

- **3 Rendering Modes:**
  - `halfblock` (Default): 2x vertical resolution using half-block characters (`▀`, `▄`) for crystal-clear silhouettes.
  - `braille`: Ultra high-resolution rendering using Unicode Braille (2x4 matrix) characters.
  - `ascii`: Classic nostalgic ASCII shading (` .:-=+*#%@`).
- **Cross-Platform & Zero Extra Audio Dependencies:** Runs natively on Windows (`winmm.dll` MCI), macOS (`afplay`), and Linux (`ffplay`/`mpv`/`aplay`) with zero additional Python audio packages.
- **Flicker-Free & Ghost-Free Rendering:** Employs Alternate Screen Buffer (`\033[?1049h`), scrollback buffer purging, and dynamic resizing for a pristine, clean display at 30 FPS.
- **Automatic & Verified Download:** Automatically fetches the original Nico Nico Douga Bad Apple video over HTTPS from Archive.org with MD5 checksum verification.
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

## Installation & Usage

Required dependencies:
```bash
pip install opencv-python-headless colorama
```

To run the player:
```bash
python main.py
```

### Options & Flags

```bash
# Start with a specific mode (halfblock, ascii, braille)
python main.py --mode braille

# Disable audio
python main.py --no-audio

# Set specific terminal width/height
python main.py --width 100 --height 35
```
