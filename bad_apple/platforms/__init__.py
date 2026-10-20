"""
Platform drivers package providing strict OS isolation.
"""

import sys
from .base import (
    BaseAudioPlayer,
    BaseInputHandler,
    BasePlatform,
    BaseTerminalManager,
    DummyAudioPlayer,
)


def get_platform(audio_path: str | None = None, no_audio: bool = False) -> BasePlatform:
    """
    Factory creating the isolated platform bundle for the host operating system.
    """
    if sys.platform == "win32":
        from .windows import WindowsPlatform

        return WindowsPlatform(audio_path=audio_path, no_audio=no_audio)
    elif sys.platform == "darwin":
        from .macos import MacOSPlatform

        return MacOSPlatform(audio_path=audio_path, no_audio=no_audio)
    else:
        from .linux import LinuxPlatform

        return LinuxPlatform(audio_path=audio_path, no_audio=no_audio)


__all__ = [
    "BaseAudioPlayer",
    "BaseInputHandler",
    "BasePlatform",
    "BaseTerminalManager",
    "DummyAudioPlayer",
    "get_platform",
]
