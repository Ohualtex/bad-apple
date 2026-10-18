"""
Windows-specific terminal manager leveraging Win32 Console API and VT100 virtual processing.
"""

import ctypes
import os
import sys
from ..base import BaseTerminalManager

ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
STD_OUTPUT_HANDLE = -11


class WindowsTerminalManager(BaseTerminalManager):
    """
    Manages Windows console modes, native VT100 escape sequences, and alternate screen buffer.
    """

    def __init__(self):
        self._is_fullscreen: bool = False
        self._old_mode: int | None = None
        self._last_size: tuple[int, int] = (80, 24)
        self._kernel32 = getattr(ctypes, "windll", None) and getattr(ctypes.windll, "kernel32", None)

    def enter_fullscreen(self) -> None:
        """Enables VT100 processing, enters Alternate Screen Buffer, and hides cursor."""
        if self._kernel32:
            try:
                h_out = self._kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
                mode = ctypes.c_ulong()
                if self._kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
                    self._old_mode = mode.value
                    self._kernel32.SetConsoleMode(h_out, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
            except Exception:
                pass

        # Switch to alternate buffer, hide cursor, and clear screen & scrollback
        sys.stdout.write("\033[?1049h\033[?25l\033[H\033[2J\033[3J")
        sys.stdout.flush()
        self._is_fullscreen = True
        self._last_size = self.get_size()

    def leave_fullscreen(self) -> None:
        """Restores cursor, colors, and switches back to Primary Screen Buffer."""
        if self._is_fullscreen:
            sys.stdout.write("\033[?25h\033[0m\033[?1049l\n")
            sys.stdout.flush()
            self._is_fullscreen = False

    def get_size(self) -> tuple[int, int]:
        """Returns terminal dimensions as (columns, lines)."""
        try:
            sz = os.get_terminal_size()
            return sz.columns, sz.lines
        except Exception:
            return 80, 24

    def check_resized(self) -> bool:
        """Detects if terminal dimensions changed since last check."""
        current_size = self.get_size()
        if current_size != self._last_size:
            self._last_size = current_size
            return True
        return False

    def cleanup(self) -> None:
        """Safely restores terminal mode and exits fullscreen."""
        self.leave_fullscreen()
        if self._kernel32 and self._old_mode is not None:
            try:
                h_out = self._kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
                self._kernel32.SetConsoleMode(h_out, self._old_mode)
                self._old_mode = None
            except Exception:
                pass
