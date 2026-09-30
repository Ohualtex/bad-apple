"""
Keyboard input package factory and terminal restoration utilities.
Automatically provisions the appropriate keyboard input listener based on host OS.
"""

import sys
from .base import BaseInputHandler

_global_active_handler: BaseInputHandler | None = None
_is_alt_screen_active: bool = False


def create_input_handler() -> BaseInputHandler:
    """
    Factory function instantiating the optimal non-blocking keyboard listener
    for the current platform (Windows msvcrt or POSIX termios).
    """
    global _global_active_handler

    if sys.platform == "win32":
        from .windows import WindowsInputHandler

        handler = WindowsInputHandler()
    else:
        from .posix import PosixInputHandler

        handler = PosixInputHandler()

    _global_active_handler = handler
    return handler


def enter_alternate_screen() -> None:
    """
    Switches to the Alternate Screen Buffer, hides cursor, and clears screen & scrollback.
    """
    global _is_alt_screen_active
    sys.stdout.write("\033[?1049h\033[?25l\033[H\033[2J\033[3J")
    sys.stdout.flush()
    _is_alt_screen_active = True


def restore_terminal(handler: BaseInputHandler | None = None) -> None:
    """
    Restores original terminal attributes, re-enables cursor visibility,
    and switches out of the Alternate Screen Buffer back to the main terminal.
    Ensures idempotency so subsequent calls do not resend \033[?1049l and jump cursor.
    """
    global _global_active_handler, _is_alt_screen_active
    target = handler or _global_active_handler
    if target:
        try:
            target.restore()
        except Exception:
            pass

    if _is_alt_screen_active:
        # Show cursor (\033[?25h), reset colors (\033[0m), exit alternate screen (\033[?1049l)
        sys.stdout.write("\033[?25h\033[0m\033[?1049l\n")
        sys.stdout.flush()
        _is_alt_screen_active = False
    else:
        # Already in primary buffer; only ensure cursor visibility and default styling
        sys.stdout.write("\033[?25h\033[0m")
        sys.stdout.flush()


# Backward-compatible alias
InputHandler = create_input_handler

__all__ = [
    "BaseInputHandler",
    "create_input_handler",
    "enter_alternate_screen",
    "InputHandler",
    "restore_terminal",
]
