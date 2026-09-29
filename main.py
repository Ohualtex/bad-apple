import argparse
import atexit
import importlib
import os
import re
import shutil
import subprocess
import sys
import time

# Suppress pygame welcome banner on CLI
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Auto-install missing dependencies for a seamless zero-setup experience
REQUIRED_PACKAGES = {
    "cv2": "opencv-python-headless",
    "colorama": "colorama",
    "pygame": "pygame",
}


def ensure_dependencies():
    """Checks for required third-party packages and auto-installs them via pip if missing."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    missing = []
    for module_name, package_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        print(f"[*] Missing dependencies detected: {', '.join(missing)}")
        print("[*] Automatically installing required packages via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print("[+] All dependencies installed successfully!\n")
        except Exception as exc:
            print(f"[!] Warning: Automatic dependency installation failed: {exc}", file=sys.stderr)
            print(f"[!] Please manually install them using: pip install {' '.join(missing)}", file=sys.stderr)


ensure_dependencies()

try:
    import msvcrt
except ImportError:
    msvcrt = None

import colorama
import cv2

from audio import AudioPlayer
from download import download_audio, download_video
from renderer import TerminalRenderer


_global_input_handler = None


class InputHandler:
    """
    Cross-platform non-blocking keyboard input listener supporting
    Windows (msvcrt) and POSIX systems / Linux / macOS (termios / select).
    """

    def __init__(self):
        self.is_windows = os.name == "nt"
        self._old_settings = None
        self._fd = None
        self._termios = None

        if not self.is_windows:
            try:
                import termios

                self._termios = termios
                self._fd = sys.stdin.fileno()
                self._old_settings = self._termios.tcgetattr(self._fd)
                # Create raw/non-canonical settings without ECHO to prevent key escape sequences leaking
                attrs = self._termios.tcgetattr(self._fd)
                attrs[3] = attrs[3] & ~(self._termios.ICANON | self._termios.ECHO)
                attrs[6][self._termios.VMIN] = 0
                attrs[6][self._termios.VTIME] = 0
                self._termios.tcsetattr(self._fd, self._termios.TCSANOW, attrs)
            except Exception:
                self._termios = None

    def get_key(self) -> str | None:
        """
        Polls for a key press without blocking.
        Returns normalized key names: 'SPACE', 'QUIT', 'MODE', 'RESTART', 'LEFT', 'RIGHT' or None.
        """
        if self.is_windows:
            if msvcrt and msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    sub = msvcrt.getch()
                    if sub == b"M":
                        return "RIGHT"
                    elif sub == b"K":
                        return "LEFT"
                    return None
                elif ch == b" ":
                    return "SPACE"
                elif ch in (b"q", b"Q", b"\x1b"):
                    return "QUIT"
                elif ch in (b"m", b"M"):
                    return "MODE"
                elif ch in (b"r", b"R"):
                    return "RESTART"
            return None
        else:
            if not self._termios or self._fd is None:
                return None
            import select

            rlist, _, _ = select.select([self._fd], [], [], 0)
            if not rlist:
                return None

            try:
                buf = os.read(self._fd, 32)
            except (OSError, BlockingIOError):
                return None

            if not buf:
                return None

            # If an escape sequence starts with \x1b, check for trailing bytes
            if buf == b"\x1b":
                r2, _, _ = select.select([self._fd], [], [], 0.02)
                if r2:
                    try:
                        buf += os.read(self._fd, 31)
                    except (OSError, BlockingIOError):
                        pass

            if buf == b" ":
                return "SPACE"
            elif buf in (b"q", b"Q"):
                return "QUIT"
            elif buf in (b"m", b"M"):
                return "MODE"
            elif buf in (b"r", b"R"):
                return "RESTART"
            elif buf == b"\x1b":
                return "QUIT"
            # Support ANSI (\x1b[C), SS3 (\x1bOC), and terminal modifier variants
            elif buf in (b"\x1b[C", b"\x1bOC") or (buf.startswith(b"\x1b") and buf.endswith(b"C")):
                return "RIGHT"
            elif buf in (b"\x1b[D", b"\x1bOD") or (buf.startswith(b"\x1b") and buf.endswith(b"D")):
                return "LEFT"

            return None

    def restore(self):
        """Restores original terminal attributes on POSIX systems."""
        if not self.is_windows and self._termios and self._old_settings and self._fd is not None:
            try:
                self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass


def restore_terminal():
    """Restores terminal settings, cursor visibility, and main screen buffer."""
    global _global_input_handler
    if _global_input_handler:
        _global_input_handler.restore()
    sys.stdout.write("\033[?25h\033[0m\033[?1049l\n")
    sys.stdout.flush()


def format_time(seconds: float) -> str:
    """Formats seconds into MM:SS display."""
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins:02d}:{secs:02d}"


def create_progress_bar(current: int, total: int, bar_length: int = 14) -> str:
    """Creates a sleek visual progress scrubber bar: ━━━━●──────────"""
    if total <= 0:
        return f"\033[90m{'─' * bar_length}\033[0m"
    ratio = min(1.0, max(0.0, current / total))
    pos = int(ratio * (bar_length - 1))
    left = "━" * pos
    head = "●"
    right = "─" * (bar_length - 1 - pos)
    return f"\033[97m{left}{head}\033[90m{right}\033[0m"


def play_bad_apple(
    video_path: str = "bad_apple.mp4",
    audio_path: str = "bad_apple.mp3",
    mode: str = "halfblock",
    enable_audio: bool = True,
    target_width: int = None,
    target_height: int = None,
):
    """Main playback loop for the Bad Apple terminal player."""
    # Verify / download video file
    if not os.path.exists(video_path):
        print(f"[*] '{video_path}' not found, starting automatic download...")
        download_video(video_path)

    # Verify / download audio file
    if enable_audio and not os.path.exists(audio_path):
        print(f"[*] '{audio_path}' not found, starting automatic download...")
        download_audio(audio_path)

    # Initialize video capture
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[!] Error: Unable to open '{video_path}'.", file=sys.stderr)
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 6573
    duration = total_frames / fps

    # Initialize terminal
    colorama.init()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    atexit.register(restore_terminal)

    # Switch to Alternate Screen Buffer, hide cursor, and clear screen & scrollback
    sys.stdout.write("\033[?1049h\033[?25l\033[H\033[2J\033[3J")
    sys.stdout.flush()

    # Prepare audio player
    audio_player = AudioPlayer(audio_path) if enable_audio else None
    if audio_player:
        audio_player.start()

    renderer = TerminalRenderer(mode=mode, target_width=target_width, target_height=target_height)
    last_terminal_size = shutil.get_terminal_size()
    global _global_input_handler
    input_handler = InputHandler()
    _global_input_handler = input_handler

    current_frame_idx = 0
    playback_start_time = time.perf_counter()
    is_paused = False
    pause_start_time = 0.0

    mode_list = TerminalRenderer.MODES
    mode_idx = mode_list.index(mode) if mode in mode_list else 0

    try:
        while True:
            # 1. Process keyboard inputs (Cross-platform)
            key = input_handler.get_key()
            if key == "RIGHT":  # Seek +5s
                new_frame = min(total_frames - 1, current_frame_idx + int(5 * fps))
                cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                current_frame_idx = new_frame
                now = time.perf_counter()
                playback_start_time = now - (current_frame_idx / fps)
                if audio_player:
                    audio_player.seek(current_frame_idx / fps)
            elif key == "LEFT":  # Seek -5s
                new_frame = max(0, current_frame_idx - int(5 * fps))
                cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                current_frame_idx = new_frame
                now = time.perf_counter()
                playback_start_time = now - (current_frame_idx / fps)
                if audio_player:
                    audio_player.seek(current_frame_idx / fps)
            elif key == "QUIT":  # Exit (Q or ESC)
                break
            elif key == "SPACE":  # Pause / Resume
                is_paused = not is_paused
                if is_paused:
                    pause_start_time = time.perf_counter()
                    if audio_player:
                        audio_player.pause()
                else:
                    pause_duration = time.perf_counter() - pause_start_time
                    playback_start_time += pause_duration
                    if audio_player:
                        audio_player.resume()
            elif key == "MODE":  # Switch mode
                mode_idx = (mode_idx + 1) % len(mode_list)
                renderer.mode = mode_list[mode_idx]
            elif key == "RESTART":  # Restart from beginning
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                current_frame_idx = 0
                playback_start_time = time.perf_counter()
                if audio_player:
                    audio_player.seek(0)
                    audio_player.resume()
                is_paused = False

            # If paused, sleep briefly
            if is_paused:
                time.sleep(0.05)
                continue

            # 2. Audio-Video Synchronization
            now = time.perf_counter()
            elapsed = now - playback_start_time
            target_frame_idx = int(elapsed * fps)

            if target_frame_idx >= total_frames:
                break

            # If lagging behind the target frame, skip frames
            if target_frame_idx > current_frame_idx + 1:
                if target_frame_idx - current_frame_idx > 5:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
                else:
                    while current_frame_idx < target_frame_idx:
                        cap.grab()
                        current_frame_idx += 1

            ret, frame = cap.read()
            if not ret:
                break
            current_frame_idx += 1

            # 3. Check for terminal resize (Responsive Resizing)
            current_terminal_size = shutil.get_terminal_size()
            if current_terminal_size != last_terminal_size:
                last_terminal_size = current_terminal_size
                # Reset cursor, clear visible viewport and erase scrollback history
                sys.stdout.write("\033[H\033[2J\033[3J")
                sys.stdout.flush()

            # 4. Render Frame
            rendered_str = renderer.render_frame(frame)

            # 5. Status Bar with Visual Scrubber
            cur_time_str = format_time(current_frame_idx / fps)
            tot_time_str = format_time(duration)
            mode_display = {
                "halfblock": "Half Block",
                "ascii": "ASCII     ",
                "braille": "Braille   ",
            }.get(renderer.mode, f"{renderer.mode:<10}")

            cols = current_terminal_size.columns
            if cols < 85:
                bar_len = 8
                controls_str = "[Space: || | Q: Quit]"
            elif cols < 110:
                bar_len = 12
                controls_str = "[Space: Pause | M: Mode | Q: Quit]"
            else:
                bar_len = 16
                controls_str = "[Space: Pause | M: Mode | ←/→: Seek | Q: Quit]"

            bar_widget = create_progress_bar(current_frame_idx, total_frames, bar_length=bar_len)

            status_content = (
                f"\033[90m[{cur_time_str}/{tot_time_str}] "
                f"{bar_widget} "
                f"\033[90m[Frame: {current_frame_idx}/{total_frames} | "
                f"Mode: \033[97m{mode_display}\033[90m] "
                f"{controls_str}\033[0m"
            )

            # Center status bar and clear to end of line to prevent leftover characters
            visible_len = len(re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", status_content))
            bar_pad = " " * max(0, (cols - visible_len) // 2)
            status_bar = f"{bar_pad}{status_content}\033[K"

            # 6. Write buffer to terminal in one write (Flicker-Free)
            sys.stdout.write(f"\033[H{rendered_str}\n{status_bar}")
            sys.stdout.flush()

            # 6. Precision Framerate Timing
            next_frame_time = (current_frame_idx + 1) / fps
            remaining = next_frame_time - (time.perf_counter() - playback_start_time)
            if remaining > 0.002:
                time.sleep(remaining)

    except KeyboardInterrupt:
        pass
    finally:
        if audio_player:
            audio_player.stop()
        cap.release()
        restore_terminal()
        print("\n[✓] Playback ended.")


def main():
    parser = argparse.ArgumentParser(
        description="Bad Apple!! Terminal ASCII & Unicode Player",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["halfblock", "ascii", "braille"],
        default="halfblock",
        help="Visual render mode: halfblock (crisp), ascii (classic), braille (ultra high res)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Disables audio output",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Target display width (default: automatic terminal width)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Target display height (default: automatic terminal height)",
    )
    parser.add_argument(
        "--file",
        default="bad_apple.mp4",
        help="Path to the video file",
    )
    parser.add_argument(
        "--audio",
        default="bad_apple.mp3",
        help="Path to the audio file",
    )

    args = parser.parse_args()
    play_bad_apple(
        video_path=args.file,
        audio_path=args.audio,
        mode=args.mode,
        enable_audio=not args.no_audio,
        target_width=args.width,
        target_height=args.height,
    )


if __name__ == "__main__":
    main()
