"""
Universal hardware-accelerated audio backend using pygame.mixer.
Provides distortion-free seeking, smooth pause/resume, and zero audio popping.
"""

import os
import sys
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
            # macOS CoreAudio requires 4096 buffer to avoid buffer underruns and pause crackling
            buf_size = 4096 if sys.platform == "darwin" else 1024
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=buf_size)
            except Exception:
                try:
                    pygame.mixer.init(buffer=buf_size)
                except Exception:
                    pygame.mixer.init()

        self._seek_offset = 0.0
        self._paused_pos = 0.0

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
            self._seek_offset = 0.0
            self._paused_pos = 0.0
            self.is_open = True
            self.is_paused = False
        except Exception:
            self.is_open = False

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            try:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    self._paused_pos = self._seek_offset + (pos_ms / 1000.0)

                # Mute momentarily on macOS to guarantee zero audio pop/crackle on CoreAudio stream pause
                if sys.platform == "darwin":
                    pygame.mixer.music.set_volume(0.0)
                    pygame.mixer.music.pause()
                    pygame.mixer.music.set_volume(1.0)
                else:
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
            target_sec = max(0.0, float(seconds))
            self._seek_offset = target_sec
            self._paused_pos = target_sec
            try:
                pygame.mixer.music.play(start=target_sec)
                if self.is_paused:
                    if sys.platform == "darwin":
                        pygame.mixer.music.set_volume(0.0)
                        pygame.mixer.music.pause()
                        pygame.mixer.music.set_volume(1.0)
                    else:
                        pygame.mixer.music.pause()
            except Exception:
                pass

    def get_time(self) -> float | None:
        """Returns the current audio playback position in seconds with millisecond precision."""
        if not self.is_open:
            return None
        if self.is_paused:
            return self._paused_pos
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms < 0:
            return None
        return self._seek_offset + (pos_ms / 1000.0)

    def stop(self) -> None:
        if self.is_open:
            try:
                if sys.platform == "darwin":
                    pygame.mixer.music.set_volume(0.0)
                    pygame.mixer.music.stop()
                    pygame.mixer.music.set_volume(1.0)
                else:
                    pygame.mixer.music.stop()
            except Exception:
                pass
            self.is_open = False
            self.is_paused = False
            self._seek_offset = 0.0
            self._paused_pos = 0.0

    def __del__(self):
        super().__del__()
