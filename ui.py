"""
UI formatting and HUD status bar renderer for the Bad Apple terminal player.
"""

import re


def format_time(seconds: float) -> str:
    """Formats seconds into MM:SS display."""
    seconds = max(0.0, seconds)
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins:02d}:{secs:02d}"


def create_progress_bar(current: int, total: int, bar_length: int = 14) -> str:
    """Creates a sleek visual progress scrubber bar with seamless box-drawing alignment."""
    if bar_length <= 0:
        return ""
    if total <= 0:
        return f"\033[90m{'─' * bar_length}\033[0m"
    ratio = min(1.0, max(0.0, current / total))
    filled_len = int(round(ratio * bar_length))
    filled_len = min(bar_length, max(0, filled_len))
    unfilled_len = bar_length - filled_len
    left = "━" * filled_len
    right = "─" * unfilled_len
    return f"\033[97m{left}\033[90m{right}\033[0m"


def render_status_bar(
    current_frame: int,
    total_frames: int,
    fps: float,
    duration: float,
    mode: str,
    terminal_columns: int,
    is_paused: bool = False,
) -> str:
    """
    Renders an adaptive, centered status bar widget with a live progress scrubber,
    playback timestamps, render mode indicators, and context-sensitive shortcut hints.
    """
    cur_time = (current_frame / fps) if fps > 0 else 0.0
    cur_time_str = format_time(cur_time)
    tot_time_str = format_time(max(0.0, duration))
    mode_name = {
        "halfblock": "HalfBlock",
        "ascii": "ASCII",
        "braille": "Braille",
    }.get(mode, mode.capitalize())

    cols = terminal_columns
    pause_badge = "\033[1;33m[PAUSED]\033[0m " if is_paused else ""

    if cols < 75:
        bar_len = 6
        controls_str = "[Space:▶ Q:Quit]" if is_paused else "[Space:|| Q:Quit]"
        info_str = f"{pause_badge}[{mode_name}]"
    elif cols < 95:
        bar_len = 8
        controls_str = "[Space:▶ Q:Quit]" if is_paused else "[Space:|| Q:Quit]"
        info_str = f"{pause_badge}[Frame: {current_frame}/{total_frames} | {mode_name}]"
    elif cols < 115:
        bar_len = 12
        controls_str = "[Space: Resume | Q: Quit]" if is_paused else "[Space: Pause | Q: Quit]"
        info_str = f"{pause_badge}[Frame: {current_frame}/{total_frames} | Mode: {mode_name}]"
    else:
        bar_len = 16
        controls_str = (
            "[Space: Resume | M: Mode | ←/→: Seek | Q: Quit]"
            if is_paused
            else "[Space: Pause | M: Mode | ←/→: Seek | Q: Quit]"
        )
        info_str = f"{pause_badge}[Frame: {current_frame}/{total_frames} | Mode: {mode_name}]"

    bar_widget = create_progress_bar(current_frame, total_frames, bar_length=bar_len)

    status_content = (
        f"\033[90m[{cur_time_str}/{tot_time_str}] "
        f"{bar_widget} "
        f"\033[90m{info_str} "
        f"{controls_str}\033[0m"
    )

    # Center status bar and clear to end of line to prevent leftover characters
    visible_len = len(re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", status_content))
    bar_pad = " " * max(0, (cols - visible_len) // 2)
    return f"{bar_pad}{status_content}\033[K"
