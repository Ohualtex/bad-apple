"""
Windows-native audio player using Media Control Interface (winmm.dll / MCI).
Requires zero external dependencies on Windows.
"""

import ctypes
import os
import sys
from .base import BaseAudioPlayer


class WindowsMciAudioPlayer(BaseAudioPlayer):
    """
    Zero-dependency audio player leveraging winmm.dll mciSendStringW API.
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        super().__init__(media_path)
        if sys.platform != "win32":
            raise RuntimeError("WindowsMciAudioPlayer is only supported on Windows.")

        self.alias = f"bad_apple_audio_{id(self)}"
        self._winmm = getattr(ctypes.windll, "winmm", None)
        if not self._winmm:
            raise RuntimeError("Failed to load winmm.dll on Windows.")

    @classmethod
    def is_available(cls) -> bool:
        """Checks if current platform is Windows with winmm available."""
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
            self._send_mci(f"set {self.alias} time format milliseconds")
            self._send_mci(f"play {self.alias}")
            self.is_paused = False

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            self._send_mci(f"pause {self.alias}")
            self.is_paused = True

    def resume(self) -> None:
        if self.is_open and self.is_paused:
            self._send_mci(f"resume {self.alias}")
            self.is_paused = False

    def seek(self, seconds: float) -> None:
        if self.is_open:
            ms = int(max(0.0, seconds) * 1000)
            self._send_mci(f"seek {self.alias} to {ms}")
            if not self.is_paused:
                self._send_mci(f"play {self.alias}")

    def stop(self) -> None:
        if self.is_open:
            self._send_mci(f"stop {self.alias}")
            self._send_mci(f"close {self.alias}")
            self.is_open = False
            self.is_paused = False

    def get_time(self) -> float | None:
        """
        Returns the current playback position in seconds via MCI status query.
        """
        if not self.is_open or not self._winmm:
            return None
        buf = ctypes.create_unicode_buffer(128)
        res = self._winmm.mciSendStringW(f"status {self.alias} position", buf, 128, 0)
        if res == 0:
            try:
                return float(buf.value) / 1000.0
            except (ValueError, TypeError):
                pass
        return None

