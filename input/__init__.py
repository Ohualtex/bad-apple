"""
Keyboard input package factory and terminal restoration utilities.
Automatically provisions the appropriate keyboard input listener based on host OS.
"""

import sys
from .base import BaseInputHandler

_global_active_handler: BaseInputHandler | None = None


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


def restore_terminal(handler: BaseInputHandler | None = None) -> None:
    """
    Restores original terminal attributes, re-enables cursor visibility,
    and switches out of the Alternate Screen Buffer back to the main terminal.
    """
    global _global_active_handler
    target = handler or _global_active_handler
    if target:
        try:
            target.restore()
        except Exception:
            pass

    # Show cursor (\033[?25h), reset colors (\033[0m), exit alternate screen (\033[?1049l)
    sys.stdout.write("\033[?25h\033[0m\033[?1049l\n")
    sys.stdout.flush()


# Backward-compatible alias
InputHandler = create_input_handler

__all__ = [
    "BaseInputHandler",
    "create_input_handler",
    "InputHandler",
    "restore_terminal",
]
