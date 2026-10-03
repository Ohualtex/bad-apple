"""
Audio package factory and unified interface.
Automatically provisions the best audio backend for the host operating system.
"""

import sys
from .base import BaseAudioPlayer
from .pygame_backend import PygameAudioPlayer
from .windows import WindowsMciAudioPlayer
from .macos import MacAfplayAudioPlayer
from .linux import LinuxAudioPlayer


class DummyAudioPlayer(BaseAudioPlayer):
    """Fallback silent audio player when no backend is available."""

    def start(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def seek(self, seconds: float) -> None:
        pass

    def stop(self) -> None:
        pass


def create_audio_player(media_path: str = "bad_apple.mp3") -> BaseAudioPlayer:
    """
    Factory function that detects system capabilities and instantiates
    the optimal audio backend.

    Priority:
    1. PygameAudioPlayer (Hardware-accelerated, flawless pause/resume, seeking)
    2. Platform-native zero-dependency fallback:
       - Windows: WindowsMciAudioPlayer (winmm.dll)
       - macOS: MacAfplayAudioPlayer (afplay with CoreAudio SIGINT teardown)
       - Linux: LinuxAudioPlayer (ffplay / mpv / paplay / aplay)
    3. DummyAudioPlayer (Silent safe fallback)
    """
    # 1. Try Pygame (Universal #1 priority)
    if PygameAudioPlayer.is_available():
        try:
            return PygameAudioPlayer(media_path)
        except Exception:
            pass

    # 2. Platform-specific fallbacks
    if sys.platform == "win32" and WindowsMciAudioPlayer.is_available():
        try:
            return WindowsMciAudioPlayer(media_path)
        except Exception:
            pass

    elif sys.platform == "darwin":
        # On macOS, prioritize ffplay/mpv if installed (superior seeking and clean pause/resume)
        if LinuxAudioPlayer.is_available():
            try:
                return LinuxAudioPlayer(media_path)
            except Exception:
                pass
        if MacAfplayAudioPlayer.is_available():
            try:
                return MacAfplayAudioPlayer(media_path)
            except Exception:
                pass

    elif (sys.platform.startswith("linux") or sys.platform.startswith("freebsd")) and LinuxAudioPlayer.is_available():
        try:
            return LinuxAudioPlayer(media_path)
        except Exception:
            pass

    # 3. Safe fallback
    return DummyAudioPlayer(media_path)


# Backward-compatible alias for existing imports:
AudioPlayer = create_audio_player

__all__ = [
    "BaseAudioPlayer",
    "PygameAudioPlayer",
    "WindowsMciAudioPlayer",
    "MacAfplayAudioPlayer",
    "LinuxAudioPlayer",
    "DummyAudioPlayer",
    "create_audio_player",
    "AudioPlayer",
]
