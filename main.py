"""
Bad Apple!! Terminal ASCII & Unicode Player
High-performance, OS-agnostic terminal playback driven by Audio Master Clock.
"""

import argparse
import os
import sys
import time

# Suppress pygame welcome banner on CLI
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from cache import BinaryCacheBuilder, BinaryCacheReader
from download import (
    DEFAULT_AUDIO_NAME,
    DEFAULT_CACHE_NAME,
    download_audio,
    download_binary_cache,
    download_video,
    get_asset_path,
)
from platforms import get_platform
from renderer import TerminalRenderer
from ui import render_status_bar


def play_bad_apple(
    mode: str = "ascii",
    enable_audio: bool = True,
    target_width: int | None = None,
    target_height: int | None = None,
) -> None:
    """
    Main playback loop driven strictly by the Audio Master Clock.
    Entirely OS-agnostic, zero-CPU binary cache rendering, zero OpenCV runtime dependency.
    """
    cache_path = get_asset_path(DEFAULT_CACHE_NAME)
    audio_path = get_asset_path(DEFAULT_AUDIO_NAME)

    # 1. Ensure binary cache asset is available
    if not os.path.exists(cache_path):
        print(f"[*] Bad Apple binary cache not found locally. Downloading to '{cache_path}'...")
        try:
            download_binary_cache(cache_path)
        except Exception as e:
            print(f"[!] Error: Failed to download binary cache ({e}). Exiting.", file=sys.stderr)
            return

    # 2. Ensure audio asset is available if audio is enabled
    if enable_audio and not os.path.exists(audio_path):
        print(f"[*] Bad Apple audio not found locally. Downloading to '{audio_path}'...")
        try:
            download_audio(audio_path)
        except Exception as e:
            print(f"[*] Warning: Audio download failed ({e}). Proceeding muted.", file=sys.stderr)
            enable_audio = False

    # 3. Read metadata from binary cache container
    try:
        with BinaryCacheReader(cache_path) as probe:
            fps = probe.fps
            total_frames = probe.total_frames
            duration = probe.duration
    except Exception as e:
        print(f"[!] Error: Corrupt or invalid binary cache ({e}). Exiting.", file=sys.stderr)
        return

    renderer = TerminalRenderer(mode=mode, target_width=target_width, target_height=target_height)
    mode_list = TerminalRenderer.MODES
    mode_idx = mode_list.index(mode) if mode in mode_list else 0

    while True:
        # Initialize OS-isolated platform driver bundle
        platform = get_platform(audio_path=audio_path if enable_audio else None, no_audio=not enable_audio)

        platform.terminal.enter_fullscreen()
        platform.audio.start()

        finished_naturally = False
        is_paused = False
        needs_redraw = True
        last_rendered_frame_idx = -1

        try:
            with BinaryCacheReader(cache_path) as cache_reader:
                while True:
                    # 1. Non-blocking keyboard input polling
                    key = platform.input.poll_key()
                    if key:
                        if key == "QUIT":
                            break
                        elif key == "SPACE":
                            is_paused = not is_paused
                            if is_paused:
                                platform.audio.pause()
                            else:
                                platform.audio.resume()
                            needs_redraw = True
                        elif key == "LEFT":
                            new_time = max(0.0, platform.audio.get_pos() - 5.0)
                            platform.audio.seek(new_time)
                            needs_redraw = True
                        elif key == "RIGHT":
                            new_time = min(duration - 0.1, platform.audio.get_pos() + 5.0)
                            platform.audio.seek(new_time)
                            needs_redraw = True
                        elif key == "MODE":
                            mode_idx = (mode_idx + 1) % len(mode_list)
                            renderer.mode = mode_list[mode_idx]
                            needs_redraw = True
                        elif key == "RESTART":
                            platform.audio.seek(0.0)
                            if not is_paused:
                                platform.audio.resume()
                            needs_redraw = True

                    # 2. Responsive Terminal Resizing (detects size change and clears ghost characters)
                    if platform.terminal.check_resized():
                        sys.stdout.write("\033[H\033[2J\033[3J")
                        sys.stdout.flush()
                        needs_redraw = True

                    # 3. Audio Master Clock query
                    current_time = platform.audio.get_pos()
                    if current_time >= duration:
                        finished_naturally = True
                        break

                    # 4. Paused state handling
                    if is_paused:
                        if needs_redraw:
                            frame_idx = min(total_frames - 1, max(0, int(current_time * fps)))
                            bin_frame = cache_reader.get_frame(frame_idx)
                            cols, _ = platform.terminal.get_size()
                            rendered_str = renderer.render_binary_frame(bin_frame)
                            status_bar = render_status_bar(
                                current_frame=frame_idx,
                                total_frames=total_frames,
                                fps=fps,
                                duration=duration,
                                mode=renderer.mode,
                                terminal_columns=cols,
                                is_paused=True,
                            )
                            sys.stdout.write(f"\033[H{rendered_str}\n\033[K\n{status_bar}\033[J")
                            sys.stdout.flush()
                            needs_redraw = False
                        time.sleep(0.02)
                        continue

                    # 5. Active playback: calculate current frame locked to audio clock (automatic frame-drop)
                    frame_idx = int(current_time * fps)
                    if frame_idx >= total_frames:
                        finished_naturally = True
                        break

                    if frame_idx != last_rendered_frame_idx or needs_redraw:
                        bin_frame = cache_reader.get_frame(frame_idx)
                        cols, _ = platform.terminal.get_size()
                        rendered_str = renderer.render_binary_frame(bin_frame)
                        status_bar = render_status_bar(
                            current_frame=frame_idx,
                            total_frames=total_frames,
                            fps=fps,
                            duration=duration,
                            mode=renderer.mode,
                            terminal_columns=cols,
                            is_paused=False,
                        )
                        sys.stdout.write(f"\033[H{rendered_str}\n\033[K\n{status_bar}\033[J")
                        sys.stdout.flush()
                        last_rendered_frame_idx = frame_idx
                        needs_redraw = False

                    # 6. Micro sleep to avoid 100% CPU busy-wait
                    time.sleep(0.002)

        except KeyboardInterrupt:
            finished_naturally = False
        finally:
            platform.cleanup()

        if not finished_naturally:
            print("\n[✓] Playback ended.")
            break

        print("\n[✓] Playback finished.")
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
        help="Developer utility: builds bad_apple.bin from MP4 using OpenCV and exits",
    )
    args = parser.parse_args()

    if args.width is not None and args.width < 4:
        parser.error("--width must be at least 4")
    if args.height is not None and args.height < 2:
        parser.error("--height must be at least 2")

    if args.build_cache:
        try:
            import cv2  # noqa: F401
        except ImportError:
            print("[!] Error: OpenCV ('opencv-python-headless') is required to build binary cache from MP4.", file=sys.stderr)
            return

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
    )


if __name__ == "__main__":
    main()
