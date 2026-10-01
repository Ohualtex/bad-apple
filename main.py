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

# Core dependencies needed for playback (colorama, pygame, numpy)
CORE_PACKAGES = {
    "colorama": "colorama",
    "pygame": "pygame",
    "numpy": "numpy",
}


def ensure_package(module_name: str, package_name: str) -> None:
    """Installs a specific package via pip if it cannot be imported."""
    try:
        importlib.import_module(module_name)
    except ImportError:
        print(f"[*] Package '{package_name}' is required for this operation.")
        print(f"[*] Automatically installing '{package_name}' via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"[+] '{package_name}' installed successfully!\n")
        except Exception as exc:
            print(f"[!] Warning: Failed to install '{package_name}': {exc}", file=sys.stderr)
            print(f"[!] Please manually run: pip install {package_name}", file=sys.stderr)


def ensure_core_dependencies():
    """Checks for required core packages and auto-installs them via pip if missing."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    missing = []
    for module_name, package_name in CORE_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        print(f"[*] Missing dependencies detected: {', '.join(missing)}")
        print("[*] Automatically installing required packages via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print("[+] All core dependencies installed successfully!\n")
        except Exception as exc:
            print(f"[!] Warning: Automatic dependency installation failed: {exc}", file=sys.stderr)
            print(f"[!] Please manually install them using: pip install {' '.join(missing)}", file=sys.stderr)


ensure_core_dependencies()

import colorama

from audio import create_audio_player
from cache import BinaryCacheBuilder, BinaryCacheReader
from download import (
    DEFAULT_CACHE_NAME,
    download_audio,
    download_binary_cache,
    download_video,
    get_asset_path,
)
from input import (
    create_input_handler,
    enter_alternate_screen,
    flush_input_buffer,
    restore_terminal,
)
from renderer import TerminalRenderer
from ui import render_status_bar


def play_bad_apple(
    mode: str = "ascii",
    enable_audio: bool = True,
    target_width: int = None,
    target_height: int = None,
    use_cache: bool = True,
):
    """Main playback loop for the Bad Apple terminal player."""
    video_path = get_asset_path("bad_apple.mp4")
    audio_path = get_asset_path("bad_apple.mp3")
    cache_path = get_asset_path(DEFAULT_CACHE_NAME)

    use_binary_cache = False

    if use_cache:
        if os.path.exists(cache_path):
            use_binary_cache = True
        elif not os.path.exists(video_path):
            # First-run setup: neither cache nor video exists yet.
            # Ask the user if interactive, otherwise default to yes.
            build_cache_choice = True
            if sys.stdin.isatty():
                try:
                    ans = input("Build binary cache now? (recommended) [Y/n]: ").strip().lower()
                    if ans in ("n", "no"):
                        build_cache_choice = False
                except (EOFError, KeyboardInterrupt):
                    print()
                    return

            if build_cache_choice:
                cache_downloaded = False
                # Try downloading pre-built cache from CDN first (fastest, lightweight)
                try:
                    download_binary_cache(cache_path)
                    cache_downloaded = True
                    use_binary_cache = True
                except Exception as e:
                    print(f"[*] Pre-built cache download unavailable ({e}). Falling back to local build...")

                # If CDN download didn't work (e.g. offline), build from video locally
                if not cache_downloaded:
                    ensure_package("cv2", "opencv-python-headless")
                    print(f"[*] Bad Apple video not found, downloading to '{video_path}'...")
                    download_video(video_path)
                    print(f"[*] Building BAPB binary cache into '{cache_path}'...")

                    def progress(cur, total, el):
                        pct = (cur / total) * 100
                        fps_val = cur / el if el > 0 else 0
                        sys.stdout.write(f"\r[*] Encoding frames: {cur}/{total} [{pct:.1f}%] ({fps_val:.0f} fps)")
                        sys.stdout.flush()

                    try:
                        BinaryCacheBuilder.build_cache(video_path, cache_path, progress_callback=progress)
                        print("\n[+] Binary cache successfully created!")
                        use_binary_cache = True
                    except Exception as err:
                        print(f"\n[!] Failed to build binary cache ({err}). Falling back to MP4.", file=sys.stderr)
                        use_binary_cache = False
            else:
                use_binary_cache = False
        else:
            # Video already exists and cache does not: user previously chose real-time video playback mode
            use_binary_cache = False

    if use_binary_cache:
        try:
            with BinaryCacheReader(cache_path) as probe:
                fps = probe.fps
                total_frames = probe.total_frames
                duration = probe.duration
        except Exception as e:
            print(f"[!] Warning: Failed to load binary cache ({e}). Falling back to MP4.", file=sys.stderr)
            use_binary_cache = False

    if not use_binary_cache:
        ensure_package("cv2", "opencv-python-headless")
        import cv2

        # Verify / download video file
        if not os.path.exists(video_path):
            print(f"[*] Bad Apple video not found, downloading to '{video_path}'...")
            download_video(video_path)

        # Probe video metadata
        probe_cap = cv2.VideoCapture(video_path)
        if not probe_cap.isOpened():
            print(f"[!] Error: Unable to open '{video_path}'.", file=sys.stderr)
            return

        fps = probe_cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(probe_cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 6573
        duration = total_frames / fps
        probe_cap.release()

    # Verify / download audio file
    if enable_audio and not os.path.exists(audio_path):
        print(f"[*] Bad Apple audio not found, downloading to '{audio_path}'...")
        download_audio(audio_path)

    # Initialize terminal
    colorama.init()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    atexit.register(restore_terminal)

    renderer = TerminalRenderer(mode=mode, target_width=target_width, target_height=target_height)
    audio_player = create_audio_player(audio_path) if enable_audio else None

    mode_list = TerminalRenderer.MODES
    mode_idx = mode_list.index(mode) if mode in mode_list else 0

    while True:
        # Switch to Alternate Screen Buffer, hide cursor, and clear screen & scrollback
        enter_alternate_screen()

        # Start / restart audio player
        if audio_player:
            audio_player.start()

        cache_reader = BinaryCacheReader(cache_path) if use_binary_cache else None
        if not use_binary_cache:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[!] Error: Unable to open '{video_path}'.", file=sys.stderr)
                break
        else:
            cap = None

        flush_input_buffer()
        last_terminal_size = shutil.get_terminal_size()
        input_handler = create_input_handler()

        current_frame_idx = 0
        playback_start_time = time.perf_counter()
        is_paused = False
        pause_start_time = 0.0
        finished_naturally = False

        try:
            while True:
                # 1. Process keyboard inputs (Cross-platform)
                key = input_handler.get_key()
                if key == "RIGHT":  # Seek +5s
                    new_frame = min(total_frames - 1, current_frame_idx + int(5 * fps))
                    if cap:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                    current_frame_idx = new_frame
                    now = time.perf_counter()
                    playback_start_time = now - (current_frame_idx / fps)
                    if audio_player:
                        audio_player.seek(current_frame_idx / fps)
                elif key == "LEFT":  # Seek -5s
                    new_frame = max(0, current_frame_idx - int(5 * fps))
                    if cap:
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
                    if cap:
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
                    finished_naturally = True
                    break

                # If lagging behind the target frame, skip frames
                if target_frame_idx > current_frame_idx + 1:
                    if cap:
                        if target_frame_idx - current_frame_idx > 5:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
                            current_frame_idx = target_frame_idx
                        else:
                            while current_frame_idx < target_frame_idx:
                                cap.grab()
                                current_frame_idx += 1
                    else:
                        current_frame_idx = target_frame_idx

                if cache_reader:
                    if current_frame_idx >= total_frames:
                        finished_naturally = True
                        break
                    bin_frame = cache_reader.get_frame(current_frame_idx)
                    current_frame_idx += 1
                    rendered_str = renderer.render_binary_frame(bin_frame)
                else:
                    ret, frame = cap.read()
                    if not ret:
                        finished_naturally = True
                        break
                    current_frame_idx += 1
                    rendered_str = renderer.render_frame(frame)

                # 3. Check for terminal resize (Responsive Resizing)
                current_terminal_size = shutil.get_terminal_size()
                if current_terminal_size != last_terminal_size:
                    last_terminal_size = current_terminal_size
                    # Reset cursor, clear visible viewport and erase scrollback history
                    sys.stdout.write("\033[H\033[2J\033[3J")
                    sys.stdout.flush()

                # 4. Status Bar with Visual Scrubber
                status_bar = render_status_bar(
                    current_frame=current_frame_idx,
                    total_frames=total_frames,
                    fps=fps,
                    duration=duration,
                    mode=renderer.mode,
                    terminal_columns=current_terminal_size.columns,
                )

                # 5. Write buffer to terminal with clean blank separator line (Flicker-Free)
                sys.stdout.write(f"\033[H{rendered_str}\n\033[K\n{status_bar}\033[J")
                sys.stdout.flush()

                # 6. Precision Framerate Timing
                next_frame_time = (current_frame_idx + 1) / fps
                remaining = next_frame_time - (time.perf_counter() - playback_start_time)
                if remaining > 0.002:
                    time.sleep(remaining)

        except KeyboardInterrupt:
            finished_naturally = False
        finally:
            if cache_reader:
                cache_reader.close()
            if cap:
                cap.release()
            if audio_player:
                audio_player.stop()
            restore_terminal()

        if not finished_naturally:
            print("\n[✓] Playback ended.")
            break

        print("\n[✓] Playback finished.")
        flush_input_buffer()
        try:
            choice = input("Replay? [y/n]: ").strip().lower()
            if choice in ("y", "yes"):
                continue
            else:
                print()
                break
        except (KeyboardInterrupt, EOFError):
            print()
            break


def main():
    parser = argparse.ArgumentParser(
        description="Bad Apple!! Terminal ASCII & Unicode Player",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["ascii", "braille", "halfblock"],
        default="ascii",
        help="Visual render mode: ascii (classic), braille (ultra high res), halfblock (crisp)",
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
        "--build-cache",
        action="store_true",
        help="Pre-renders and builds the bad_apple.bin binary cache for zero-CPU playback and exits",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Forces real-time OpenCV MP4 decoding, ignoring any binary cache",
    )
    args = parser.parse_args()

    if args.build_cache:
        ensure_package("cv2", "opencv-python-headless")
        video_path = get_asset_path("bad_apple.mp4")
        if not os.path.exists(video_path):
            print(f"[*] Bad Apple video not found, downloading to '{video_path}'...")
            download_video(video_path)
        cache_path = get_asset_path(DEFAULT_CACHE_NAME)
        print(f"[*] Building BAPB binary cache into '{cache_path}'...")
        def progress(cur, total, el):
            pct = (cur / total) * 100
            fps_val = cur / el if el > 0 else 0
            sys.stdout.write(f"\r[*] Encoding frames: {cur}/{total} [{pct:.1f}%] ({fps_val:.0f} fps)")
            sys.stdout.flush()
        BinaryCacheBuilder.build_cache(video_path, cache_path, progress_callback=progress)
        print("\n[+] Binary cache successfully created!")
        return

    play_bad_apple(
        mode=args.mode,
        enable_audio=not args.no_audio,
        target_width=args.width,
        target_height=args.height,
        use_cache=not args.no_cache,
    )


if __name__ == "__main__":
    main()
