"""
Windows-specific non-blocking keyboard input listener using msvcrt.
"""

import sys
from .base import BaseInputHandler

try:
    import msvcrt
except ImportError:
    msvcrt = None


class WindowsInputHandler(BaseInputHandler):
    """
    Non-blocking keyboard listener utilizing the Windows C-runtime msvcrt module.
    """

    def __init__(self):
        super().__init__()
        if sys.platform != "win32" or not msvcrt:
            raise RuntimeError("WindowsInputHandler is only supported on Windows systems.")

    def get_key(self) -> str | None:
        """
        Polls for key presses on Windows without blocking.
        Handles standard ASCII keys and extended 2-byte arrow keys.
        """
        if not msvcrt or not msvcrt.kbhit():
            return None

        ch = msvcrt.getch()

        # Handle extended keys (Arrow keys prefix: 0x00 or 0xE0)
        if ch in (b"\x00", b"\xe0"):
            sub = msvcrt.getch()
            if sub == b"M":
                return "RIGHT"
            elif sub == b"K":
                return "LEFT"
            return None

        if ch == b"\x03":
            raise KeyboardInterrupt
        elif ch == b" ":
            return "SPACE"
        elif ch in (b"q", b"Q", b"\x1b"):
            return "QUIT"
        elif ch in (b"m", b"M"):
            return "MODE"
        elif ch in (b"r", b"R"):
            return "RESTART"

        return None

    def restore(self) -> None:
        # msvcrt does not alter console mode flags that require manual cleanup
        pass
