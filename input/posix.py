"""
POSIX-compliant non-blocking keyboard input listener for macOS and Linux.
Configures raw terminal mode without ECHO to prevent ANSI leakage and parses
both standard ANSI (\\x1b[C) and macOS SS3 (\\x1bOC) arrow key escape sequences.
"""

import os
import sys
from .base import BaseInputHandler

try:
    import termios
    import select
    _HAS_POSIX_TERMINAL = True
except ImportError:
    termios = None
    select = None
    _HAS_POSIX_TERMINAL = False


class PosixInputHandler(BaseInputHandler):
    """
    POSIX terminal non-blocking keyboard listener utilizing termios and select.
    """

    def __init__(self):
        super().__init__()
        if not _HAS_POSIX_TERMINAL or sys.platform == "win32":
            raise RuntimeError("PosixInputHandler requires a POSIX system (Linux / macOS).")

        self._old_settings = None
        self._fd = None
        self._termios = termios

        try:
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
            self._fd = None

    def get_key(self) -> str | None:
        """
        Polls for key presses without blocking using select and unbuffered read.
        """
        if not self._termios or self._fd is None:
            return None

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

    def restore(self) -> None:
        """Restores original terminal attributes on POSIX systems."""
        if self._termios and self._old_settings and self._fd is not None:
            try:
                self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
            finally:
                self._old_settings = None
