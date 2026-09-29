import argparse
import atexit
import os
import sys
import time

try:
    import msvcrt
except ImportError:
    msvcrt = None

import colorama
import cv2

from audio import AudioPlayer
from download import download_audio, download_video
from renderer import TerminalRenderer


def restore_terminal():
    """Restores terminal settings and cursor visibility to normal."""
    sys.stdout.write("\033[?25h\033[0m\n")
    sys.stdout.flush()


def format_time(seconds: float) -> str:
    """Formats seconds into MM:SS display."""
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins:02d}:{secs:02d}"


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

    # Hide cursor and clear screen
    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()

    # Prepare audio player
    audio_player = AudioPlayer(audio_path) if enable_audio else None
    if audio_player:
        audio_player.start()

    renderer = TerminalRenderer(mode=mode, target_width=target_width, target_height=target_height)

    current_frame_idx = 0
    playback_start_time = time.perf_counter()
    is_paused = False
    pause_start_time = 0.0

    mode_list = TerminalRenderer.MODES
    mode_idx = mode_list.index(mode) if mode in mode_list else 0

    try:
        while True:
            # 1. Process keyboard inputs (msvcrt)
            if msvcrt and msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):  # Special keys (e.g. arrow keys)
                    sub = msvcrt.getch()
                    if sub == b"M":  # Right arrow -> +5s
                        new_frame = min(total_frames - 1, current_frame_idx + int(5 * fps))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                        current_frame_idx = new_frame
                        now = time.perf_counter()
                        playback_start_time = now - (current_frame_idx / fps)
                        if audio_player:
                            audio_player.seek(current_frame_idx / fps)
                    elif sub == b"K":  # Left arrow -> -5s
                        new_frame = max(0, current_frame_idx - int(5 * fps))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                        current_frame_idx = new_frame
                        now = time.perf_counter()
                        playback_start_time = now - (current_frame_idx / fps)
                        if audio_player:
                            audio_player.seek(current_frame_idx / fps)
                elif ch in (b"q", b"Q", b"\x1b"):  # Exit (Q or ESC)
                    break
                elif ch == b" ":  # Pause / Resume
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
                elif ch in (b"m", b"M"):  # Switch mode
                    mode_idx = (mode_idx + 1) % len(mode_list)
                    renderer.mode = mode_list[mode_idx]
                elif ch in (b"r", b"R"):  # Restart from beginning
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

            # 3. Render Frame
            rendered_str = renderer.render_frame(frame)

            # 4. Status Bar
            cur_time_str = format_time(current_frame_idx / fps)
            tot_time_str = format_time(duration)
            mode_display = {
                "halfblock": "Half Block [▀▄]",
                "ascii": "ASCII [.::*#@]",
                "braille": "Braille [⠶⠷]",
            }.get(renderer.mode, renderer.mode)

            status_bar = (
                f"\033[90m[{cur_time_str}/{tot_time_str}] "
                f"Mode: \033[97m{mode_display}\033[90m | "
                f"Frame: {current_frame_idx}/{total_frames} | "
                f"[Space: Pause | M: Mode | ←/→: Seek | Q: Quit]\033[0m"
            )

            # 5. Write buffer to terminal in one write (Flicker-Free)
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
