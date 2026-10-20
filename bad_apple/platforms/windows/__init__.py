"""
Windows platform bundle.
"""

from ..base import BaseAudioPlayer, BaseInputHandler, BasePlatform, BaseTerminalManager, DummyAudioPlayer
from .audio import create_windows_audio_player
from .input import WindowsInputHandler
from .terminal import WindowsTerminalManager


class WindowsPlatform(BasePlatform):
    """
    Platform implementation tailored for Microsoft Windows environments.
    """

    def __init__(self, audio_path: str | None = None, no_audio: bool = False):
        self._terminal = WindowsTerminalManager()
        self._input = WindowsInputHandler()

        if no_audio or not audio_path:
            self._audio = DummyAudioPlayer(audio_path or "")
        else:
            self._audio = create_windows_audio_player(audio_path)

    @property
    def audio(self) -> BaseAudioPlayer:
        return self._audio

    @property
    def input(self) -> BaseInputHandler:
        return self._input

    @property
    def terminal(self) -> BaseTerminalManager:
        return self._terminal


__all__ = ["WindowsPlatform", "WindowsTerminalManager", "WindowsInputHandler", "create_windows_audio_player"]
