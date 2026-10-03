"""
Base audio player interface defining common playback lifecycle methods.
"""

from abc import ABC, abstractmethod
import os


class BaseAudioPlayer(ABC):
    """
    Abstract base class for all platform-specific audio backends.
    Guarantees a unified API across Windows, macOS, and Linux.
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        self.media_path = os.path.abspath(media_path)
        self.is_open = False
        self.is_paused = False

    @abstractmethod
    def start(self) -> None:
        """Opens audio resource and begins playback."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Pauses current audio playback."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resumes paused audio playback."""
        pass

    @abstractmethod
    def seek(self, seconds: float) -> None:
        """Seeks to the given position in seconds."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops playback and releases all system audio resources."""
        pass

    def get_time(self) -> float | None:
        """
        Returns the current audio playback position in seconds,
        or None if unsupported or closed.
        """
        return None

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
