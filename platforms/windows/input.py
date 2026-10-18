"""
Windows console keyboard input listener using msvcrt.
"""

import msvcrt
from ..base import BaseInputHandler


class WindowsInputHandler(BaseInputHandler):
    """
    Non-blocking keyboard listener for Windows console environments.
    """

    def poll_key(self) -> str | None:
        """
        Polls for available keystrokes non-blockingly.
        Returns normalized action tokens: SPACE, LEFT, RIGHT, MODE, RESTART, QUIT.
        """
        if not msvcrt.kbhit():
            return None

        try:
            ch = msvcrt.getch()
        except Exception:
            return None

        # Two-byte extended keys (Arrow keys, function keys)
        if ch in (b"\x00", b"\xe0"):
            if not msvcrt.kbhit():
                return None
            try:
                code = msvcrt.getch()
            except Exception:
                return None

            if code == b"K":  # Left arrow
                return "LEFT"
            elif code == b"M":  # Right arrow
                return "RIGHT"
            elif code == b"H":  # Up arrow
                return "UP"
            elif code == b"P":  # Down arrow
                return "DOWN"
            return None

        # Single-byte standard ASCII keys
        if ch == b" ":
            return "SPACE"
        elif ch in (b"q", b"Q", b"\x1b"):  # Q or Escape
            return "QUIT"
        elif ch in (b"m", b"M"):
            return "MODE"
        elif ch in (b"r", b"R"):
            return "RESTART"

        return None

    def cleanup(self) -> None:
        """Discards any lingering keystrokes from console buffer."""
        try:
            while msvcrt.kbhit():
                msvcrt.getch()
        except Exception:
            pass
