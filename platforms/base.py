"""
Core abstract contracts and fallback implementations for cross-platform drivers.
"""

from abc import ABC, abstractmethod
import time


class BaseAudioPlayer(ABC):
    """
    Abstract base contract for platform-specific hardware/software audio engines.
    """

    def __init__(self, media_path: str = ""):
        self.media_path = media_path
        self.is_open: bool = False
        self.is_paused: bool = False

    @abstractmethod
    def start(self) -> None:
        """Starts audio playback from the beginning or initializes the stream."""
        ...

    @abstractmethod
    def pause(self) -> None:
        """Suspends active audio playback."""
        ...

    @abstractmethod
    def resume(self) -> None:
        """Resumes suspended audio playback."""
        ...

    @abstractmethod
    def seek(self, seconds: float) -> None:
        """Seeks audio playback to the specified timestamp in seconds."""
        ...

    @abstractmethod
    def get_pos(self) -> float:
        """
        Returns the current playback position in seconds.
        Serves as the single source of truth for the Audio Master Clock.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stops audio playback and releases underlying system audio resources."""
        ...

    @abstractmethod
    def is_playing(self) -> bool:
        """Returns True if audio is actively playing and not paused."""
        ...


class DummyAudioPlayer(BaseAudioPlayer):
    """
    Null Object implementation providing a virtual audio clock based on time.perf_counter.
    Used when audio playback is disabled (--no-audio) or unavailable.
    """

    def __init__(self, media_path: str = ""):
        super().__init__(media_path)
        self._pos: float = 0.0
        self._start_perf: float = 0.0
        self._paused: bool = False
        self._playing: bool = False

    def start(self) -> None:
        self._playing = True
        self._paused = False
        self._start_perf = time.perf_counter()
        self._pos = 0.0
        self.is_open = True
        self.is_paused = False

    def pause(self) -> None:
        if self._playing and not self._paused:
            self._pos = self.get_pos()
            self._paused = True
            self.is_paused = True

    def resume(self) -> None:
        if self._playing and self._paused:
            self._start_perf = time.perf_counter() - self._pos
            self._paused = False
            self.is_paused = False

    def seek(self, seconds: float) -> None:
        target_pos = max(0.0, float(seconds))
        self._pos = target_pos
        self._start_perf = time.perf_counter() - target_pos

    def get_pos(self) -> float:
        if not self._playing:
            return 0.0
        if self._paused:
            return self._pos
        return max(0.0, time.perf_counter() - self._start_perf)

    def stop(self) -> None:
        self._playing = False
        self._paused = False
        self._pos = 0.0
        self.is_open = False
        self.is_paused = False

    def is_playing(self) -> bool:
        return self._playing and not self._paused


class BaseInputHandler(ABC):
    """
    Abstract base contract for non-blocking console keyboard input listener.
    """

    @abstractmethod
    def poll_key(self) -> str | None:
        """
        Polls for available keystrokes in a non-blocking manner.
        Returns a normalized action token (e.g., 'SPACE', 'LEFT', 'RIGHT', 'MODE',
        'RESTART', 'QUIT') or None if no key was pressed.
        """
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Restores original console terminal input modes and flushes buffers."""
        ...


class BaseTerminalManager(ABC):
    """
    Abstract base contract for terminal window operations, alternate screen buffer,
    VT100 escape handling, and resize event tracking.
    """

    @abstractmethod
    def enter_fullscreen(self) -> None:
        """Enables VT100 processing, switches to Alternate Screen Buffer, and hides cursor."""
        ...

    @abstractmethod
    def leave_fullscreen(self) -> None:
        """Restores cursor visibility, color attributes, and switches back to Primary Screen Buffer."""
        ...

    @abstractmethod
    def get_size(self) -> tuple[int, int]:
        """Returns the current terminal window dimensions as (columns, lines)."""
        ...

    @abstractmethod
    def check_resized(self) -> bool:
        """
        Detects if the terminal window dimensions changed since the last invocation.
        Returns True if a resize occurred, False otherwise.
        """
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Guarantees terminal teardown and restoration to prevent broken terminal states."""
        ...


class BasePlatform(ABC):
    """
    Unified platform root encapsulating isolated audio, input, and terminal drivers.
    """

    @property
    @abstractmethod
    def audio(self) -> BaseAudioPlayer:
        """Returns the active platform audio player instance."""
        ...

    @property
    @abstractmethod
    def input(self) -> BaseInputHandler:
        """Returns the active platform input handler instance."""
        ...

    @property
    @abstractmethod
    def terminal(self) -> BaseTerminalManager:
        """Returns the active platform terminal manager instance."""
        ...

    def cleanup(self) -> None:
        """Performs safe, exception-guarded teardown across all platform sub-drivers."""
        try:
            self.audio.stop()
        except Exception:
            pass
        try:
            self.input.cleanup()
        except Exception:
            pass
        try:
            self.terminal.cleanup()
        except Exception:
            pass
