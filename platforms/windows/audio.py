"""
Windows-specific audio engines: Pygame hardware mixer with WinMM MCI native fallback.
"""

import ctypes
import os
import sys
from ..base import BaseAudioPlayer, DummyAudioPlayer


class WindowsMciAudioPlayer(BaseAudioPlayer):
    """
    Zero-dependency audio player leveraging Windows winmm.dll (Media Control Interface).
    Requires no external packages or binaries on Windows.
    """

    def __init__(self, media_path: str = ""):
        super().__init__(media_path)
        self.alias = f"bad_apple_audio_{id(self)}"
        self._winmm = getattr(ctypes, "windll", None) and getattr(ctypes.windll, "winmm", None)
        self._paused_pos: float = 0.0

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if running on Windows with winmm available."""
        return sys.platform == "win32" and hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm")

    def _send_mci(self, command: str) -> int:
        if not self._winmm:
            return -1
        return self._winmm.mciSendStringW(command, None, 0, 0)

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return

        self.stop()
        open_cmd = f'open "{self.media_path}" type mpegvideo alias {self.alias}'
        res = self._send_mci(open_cmd)
        if res == 0:
            self.is_open = True
            self.is_paused = False
            self._send_mci(f"set {self.alias} time format milliseconds")
            self._send_mci(f"play {self.alias}")

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            self._paused_pos = self.get_pos()
            self._send_mci(f"pause {self.alias}")
            self.is_paused = True

    def resume(self) -> None:
        if self.is_open and self.is_paused:
            self._send_mci(f"resume {self.alias}")
            self.is_paused = False

    def seek(self, seconds: float) -> None:
        if self.is_open:
            ms = int(max(0.0, float(seconds)) * 1000)
            self._send_mci(f"seek {self.alias} to {ms}")
            if not self.is_paused:
                self._send_mci(f"play {self.alias}")
            else:
                self._paused_pos = max(0.0, float(seconds))

    def get_pos(self) -> float:
        """Returns current playback position in seconds via MCI status query."""
        if not self.is_open or not self._winmm:
            return 0.0
        if self.is_paused:
            return self._paused_pos

        buf = ctypes.create_unicode_buffer(128)
        res = self._winmm.mciSendStringW(f"status {self.alias} position", buf, 128, 0)
        if res == 0:
            try:
                return float(buf.value) / 1000.0
            except (ValueError, TypeError):
                pass
        return self._paused_pos

    def stop(self) -> None:
        if self.is_open:
            self._send_mci(f"stop {self.alias}")
            self._send_mci(f"close {self.alias}")
            self.is_open = False
            self.is_paused = False
            self._paused_pos = 0.0

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused


class WindowsPygameAudioPlayer(BaseAudioPlayer):
    """
    High-precision audio playback via pygame.mixer on Windows.
    """

    def __init__(self, media_path: str = ""):
        super().__init__(media_path)
        import pygame.mixer

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            except Exception:
                pygame.mixer.init()

        self._seek_offset: float = 0.0
        self._paused_pos: float = 0.0

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pygame.mixer  # noqa: F401
            return True
        except Exception:
            return False

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return

        import pygame.mixer

        self.stop()
        try:
            pygame.mixer.music.load(self.media_path)
            pygame.mixer.music.play()
            self._seek_offset = 0.0
            self._paused_pos = 0.0
            self.is_open = True
            self.is_paused = False
        except Exception:
            self.is_open = False

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            import pygame.mixer

            try:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    self._paused_pos = self._seek_offset + (pos_ms / 1000.0)
                pygame.mixer.music.pause()
                self.is_paused = True
            except Exception:
                pass

    def resume(self) -> None:
        if self.is_open and self.is_paused:
            import pygame.mixer

            try:
                pygame.mixer.music.unpause()
                self.is_paused = False
            except Exception:
                pass

    def seek(self, seconds: float) -> None:
        if self.is_open:
            import pygame.mixer

            target_sec = max(0.0, float(seconds))
            self._seek_offset = target_sec
            self._paused_pos = target_sec
            try:
                pygame.mixer.music.play(start=target_sec)
                if self.is_paused:
                    pygame.mixer.music.pause()
            except Exception:
                pass

    def get_pos(self) -> float:
        if not self.is_open:
            return 0.0
        if self.is_paused:
            return self._paused_pos

        import pygame.mixer

        try:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms >= 0:
                return self._seek_offset + (pos_ms / 1000.0)
        except Exception:
            pass
        return self._seek_offset

    def stop(self) -> None:
        if self.is_open:
            import pygame.mixer

            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.is_open = False
            self.is_paused = False
            self._seek_offset = 0.0
            self._paused_pos = 0.0

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused


def create_windows_audio_player(media_path: str = "") -> BaseAudioPlayer:
    """
    Instantiates the optimal audio player for Windows:
    1. WindowsPygameAudioPlayer (if pygame is installed)
    2. WindowsMciAudioPlayer (native winmm.dll zero-dependency fallback)
    3. DummyAudioPlayer (fallback if audio path is missing or failed)
    """
    if WindowsPygameAudioPlayer.is_available():
        try:
            return WindowsPygameAudioPlayer(media_path)
        except Exception:
            pass

    if WindowsMciAudioPlayer.is_available():
        try:
            return WindowsMciAudioPlayer(media_path)
        except Exception:
            pass

    return DummyAudioPlayer(media_path)
