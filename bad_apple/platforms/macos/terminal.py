"""
macOS-specific terminal manager with SIGWINCH signal handling and direct ioctl size queries.
"""

import os
import signal
import sys
from ..base import BaseTerminalManager


class MacOSTerminalManager(BaseTerminalManager):
    """
    Manages macOS terminal states, VT escape sequences, SIGWINCH signals,
    and Alternate Screen Buffer.
    """

    def __init__(self):
        self._is_fullscreen: bool = False
        self._last_size: tuple[int, int] = (80, 24)
        self._resized: bool = False
        self._old_sigwinch = None

    def _on_sigwinch(self, signum, frame):
        self._resized = True

    def enter_fullscreen(self) -> None:
        """Enters Alternate Screen Buffer, hides cursor, and registers SIGWINCH handler."""
        # Enter alternate buffer, hide cursor, clear screen
        sys.stdout.write("\033[?1049h\033[?25l\033[H\033[2J\033[3J")
        sys.stdout.flush()
        self._is_fullscreen = True
        self._last_size = self.get_size()

        sigwinch = getattr(signal, "SIGWINCH", None)
        if sigwinch is not None:
            try:
                self._old_sigwinch = signal.signal(sigwinch, self._on_sigwinch)
            except Exception:
                pass

    def leave_fullscreen(self) -> None:
        """Restores cursor, default styling, and returns to Primary Screen Buffer."""
        if self._is_fullscreen:
            sys.stdout.write("\033[?25h\033[0m\033[?1049l\n")
            sys.stdout.flush()
            self._is_fullscreen = False

        if self._old_sigwinch is not None:
            sigwinch = getattr(signal, "SIGWINCH", None)
            if sigwinch is not None:
                try:
                    signal.signal(sigwinch, self._old_sigwinch)
                except Exception:
                    pass
            self._old_sigwinch = None

    def get_size(self) -> tuple[int, int]:
        """
        Queries terminal dimensions directly via kernel ioctl on stdout fd
        to prevent stale dimensions cached by macOS Terminal.app / iTerm2.
        """
        try:
            sz = os.get_terminal_size(sys.stdout.fileno())
            return sz.columns, sz.lines
        except Exception:
            try:
                sz = os.get_terminal_size()
                return sz.columns, sz.lines
            except Exception:
                return 80, 24

    def check_resized(self) -> bool:
        """Detects if terminal dimensions changed either via SIGWINCH or polling."""
        current_size = self.get_size()
        if self._resized or current_size != self._last_size:
            self._resized = False
            self._last_size = current_size
            return True
        return False

    def cleanup(self) -> None:
        """Guarantees terminal restoration on macOS."""
        self.leave_fullscreen()
