"""
Linux platform bundle.
"""

from ..base import BaseAudioPlayer, BaseInputHandler, BasePlatform, BaseTerminalManager, DummyAudioPlayer
from .audio import create_linux_audio_player
from .input import LinuxInputHandler
from .terminal import LinuxTerminalManager


class LinuxPlatform(BasePlatform):
    """
    Platform implementation tailored for GNU/Linux environments.
    """

    def __init__(self, audio_path: str | None = None, no_audio: bool = False):
        self._terminal = LinuxTerminalManager()
        self._input = LinuxInputHandler()

        if no_audio or not audio_path:
            self._audio = DummyAudioPlayer(audio_path or "")
        else:
            self._audio = create_linux_audio_player(audio_path)

    @property
    def audio(self) -> BaseAudioPlayer:
        return self._audio

    @property
    def input(self) -> BaseInputHandler:
        return self._input

    @property
    def terminal(self) -> BaseTerminalManager:
        return self._terminal


__all__ = ["LinuxPlatform", "LinuxTerminalManager", "LinuxInputHandler", "create_linux_audio_player"]
