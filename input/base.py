"""
Base input handler interface defining non-blocking keyboard polling and terminal restoration.
"""

from abc import ABC, abstractmethod


class BaseInputHandler(ABC):
    """
    Abstract base class for platform-specific non-blocking keyboard listeners.
    Normalized key outputs: 'SPACE', 'QUIT', 'MODE', 'RESTART', 'LEFT', 'RIGHT' or None.
    """

    @abstractmethod
    def get_key(self) -> str | None:
        """
        Polls for a key press without blocking.
        Returns normalized key name or None if no key was pressed.
        """
        pass

    def restore(self) -> None:
        """Restores original terminal settings if modified."""
        pass

    def __del__(self):
        try:
            self.restore()
        except Exception:
            pass
