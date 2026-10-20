"""
Linux non-blocking console keyboard input listener using termios and select.
"""

import select
import sys
from ..base import BaseInputHandler

try:
    import termios
    import tty

    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False


class LinuxInputHandler(BaseInputHandler):
    """
    Non-blocking keyboard listener for Linux terminal environments.
    """

    def __init__(self):
        self._old_settings = None
        self._is_raw: bool = False
        if _HAS_TERMIOS and sys.stdin.isatty():
            try:
                self._old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
                self._is_raw = True
            except Exception:
                pass

    def poll_key(self) -> str | None:
        """
        Polls for available keystrokes non-blockingly using select.
        Returns normalized action tokens: SPACE, LEFT, RIGHT, MODE, RESTART, QUIT.
        """
        if not _HAS_TERMIOS or not self._is_raw:
            return None

        try:
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if not rlist:
                return None
            ch = sys.stdin.read(1)
        except Exception:
            return None

        # Parse ANSI escape sequences (Arrow keys)
        if ch == "\x1b":
            try:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.005)
                if not rlist:
                    return "QUIT"  # Standalone Escape key
                seq1 = sys.stdin.read(1)
                if seq1 == "[":
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.005)
                    if not rlist:
                        return None
                    seq2 = sys.stdin.read(1)
                    if seq2 == "D":
                        return "LEFT"
                    elif seq2 == "C":
                        return "RIGHT"
                    elif seq2 == "A":
                        return "UP"
                    elif seq2 == "B":
                        return "DOWN"
            except Exception:
                return None
            return None

        if ch == " ":
            return "SPACE"
        elif ch in ("q", "Q"):
            return "QUIT"
        elif ch in ("m", "M"):
            return "MODE"
        elif ch in ("r", "R"):
            return "RESTART"

        return None

    def cleanup(self) -> None:
        """Restores original terminal attributes."""
        if _HAS_TERMIOS and self._is_raw and self._old_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
                self._is_raw = False
            except Exception:
                pass
