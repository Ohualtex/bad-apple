import argparse
import atexit
import importlib
import os
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

import colorama
import cv2

from audio import create_audio_player
from download import download_audio, download_video
from input import create_input_handler, restore_terminal
from renderer import TerminalRenderer
from ui import render_status_bar


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
    audio_player = create_audio_player(audio_path) if enable_audio else None
    if audio_player:
        audio_player.start()

    renderer = TerminalRenderer(mode=mode, target_width=target_width, target_height=target_height)
    last_terminal_size = shutil.get_terminal_size()
    input_handler = create_input_handler()

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
                    current_frame_idx = target_frame_idx
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
            status_bar = render_status_bar(
                current_frame=current_frame_idx,
                total_frames=total_frames,
                fps=fps,
                duration=duration,
                mode=renderer.mode,
                terminal_columns=current_terminal_size.columns,
            )

            # 6. Write buffer to terminal with clean blank separator line (Flicker-Free)
            sys.stdout.write(f"\033[H{rendered_str}\n\033[K\n{status_bar}\033[J")
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
