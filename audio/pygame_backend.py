"""
Universal hardware-accelerated audio backend using pygame.mixer.
Provides distortion-free seeking, smooth pause/resume, and zero audio popping.
"""

import os
from .base import BaseAudioPlayer

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

try:
    import pygame.mixer

    _HAS_PYGAME = True
except Exception:
    _HAS_PYGAME = False


class PygameAudioPlayer(BaseAudioPlayer):
    """
    Audio player utilizing pygame.mixer for high-fidelity cross-platform playback.
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        super().__init__(media_path)
        if not _HAS_PYGAME:
            raise RuntimeError("pygame is not installed or pygame.mixer failed to load.")

        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if pygame.mixer is ready for use."""
        return _HAS_PYGAME

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return

        self.stop()
        try:
            pygame.mixer.music.load(self.media_path)
            pygame.mixer.music.play()
            self.is_open = True
            self.is_paused = False
        except Exception:
            self.is_open = False

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            try:
                pygame.mixer.music.pause()
                self.is_paused = True
            except Exception:
                pass

    def resume(self) -> None:
        if self.is_open and self.is_paused:
            try:
                pygame.mixer.music.unpause()
                self.is_paused = False
            except Exception:
                pass

    def seek(self, seconds: float) -> None:
        if self.is_open:
            try:
                pygame.mixer.music.play(start=max(0.0, seconds))
                if self.is_paused:
                    pygame.mixer.music.pause()
            except Exception:
                pass

    def stop(self) -> None:
        if self.is_open:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.is_open = False
            self.is_paused = False

    def __del__(self):
        super().__del__()
