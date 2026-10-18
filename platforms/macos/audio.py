"""
macOS-specific audio engines: Pygame with CoreAudio 4096 buffer and FFplay hardware fallback.
"""

import os
import shutil
import signal
import subprocess
import time
from ..base import BaseAudioPlayer, DummyAudioPlayer


class MacOSPygameAudioPlayer(BaseAudioPlayer):
    """
    High-fidelity audio playback via pygame.mixer on macOS.
    Configured with 4096 buffer and volume dampening to prevent CoreAudio pops and crackles.
    """

    def __init__(self, media_path: str = ""):
        super().__init__(media_path)
        import pygame.mixer

        if not pygame.mixer.get_init():
            try:
                # 4096 buffer is required on CoreAudio to avoid buffer underrun crackles
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
            except Exception:
                try:
                    pygame.mixer.init(buffer=4096)
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

                # Mute momentarily to guarantee zero audio crackle on CoreAudio stream pause
                pygame.mixer.music.set_volume(0.0)
                pygame.mixer.music.pause()
                pygame.mixer.music.set_volume(1.0)
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
                    pygame.mixer.music.set_volume(0.0)
                    pygame.mixer.music.pause()
                    pygame.mixer.music.set_volume(1.0)
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


class MacOSFFplayAudioPlayer(BaseAudioPlayer):
    """
    Hardware-accelerated audio player using system ffplay binary.
    Uses SIGSTOP/SIGCONT signals for zero-CPU pause/resume and fast in-flight seek.
    """

    def __init__(self, media_path: str = ""):
        super().__init__(media_path)
        self._proc: subprocess.Popen | None = None
        self._start_perf: float = 0.0
        self._seek_offset: float = 0.0
        self._paused_pos: float = 0.0

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ffplay") is not None

    def _spawn(self, start_sec: float = 0.0) -> None:
        self._teardown_proc()
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
        if start_sec > 0:
            cmd.extend(["-ss", f"{start_sec:.3f}"])
        cmd.append(self.media_path)

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._start_perf = time.perf_counter()
            self._seek_offset = start_sec
            self.is_open = True
            self.is_paused = False
        except Exception:
            self._proc = None
            self.is_open = False

    def _teardown_proc(self) -> None:
        if self._proc is not None:
            try:
                if self.is_paused:
                    sig_cont = getattr(signal, "SIGCONT", None)
                    if sig_cont is not None:
                        os.kill(self._proc.pid, sig_cont)
                self._proc.terminate()
                self._proc.wait(timeout=0.5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return
        self._spawn(0.0)

    def pause(self) -> None:
        if self._proc and self._proc.poll() is None and not self.is_paused:
            sig_stop = getattr(signal, "SIGSTOP", None)
            if sig_stop is not None:
                try:
                    self._paused_pos = self.get_pos()
                    os.kill(self._proc.pid, sig_stop)
                    self.is_paused = True
                except Exception:
                    pass

    def resume(self) -> None:
        if self._proc and self._proc.poll() is None and self.is_paused:
            sig_cont = getattr(signal, "SIGCONT", None)
            if sig_cont is not None:
                try:
                    os.kill(self._proc.pid, sig_cont)
                    self._start_perf = time.perf_counter()
                    self._seek_offset = self._paused_pos
                    self.is_paused = False
                except Exception:
                    pass

    def seek(self, seconds: float) -> None:
        target_sec = max(0.0, float(seconds))
        was_paused = self.is_paused
        self._spawn(target_sec)
        if was_paused:
            self.pause()

    def get_pos(self) -> float:
        if not self.is_open or self._proc is None:
            return 0.0
        if self.is_paused:
            return self._paused_pos
        return max(0.0, self._seek_offset + (time.perf_counter() - self._start_perf))

    def stop(self) -> None:
        self._teardown_proc()
        self.is_open = False
        self.is_paused = False
        self._seek_offset = 0.0
        self._paused_pos = 0.0

    def is_playing(self) -> bool:
        return self._proc is not None and self._proc.poll() is None and not self.is_paused


def create_macos_audio_player(media_path: str = "") -> BaseAudioPlayer:
    """
    Instantiates the optimal audio player for macOS:
    1. MacOSPygameAudioPlayer (CoreAudio 4096 buffer)
    2. MacOSFFplayAudioPlayer (SIGSTOP/SIGCONT hardware acceleration)
    3. DummyAudioPlayer (fallback)
    """
    if MacOSPygameAudioPlayer.is_available():
        try:
            return MacOSPygameAudioPlayer(media_path)
        except Exception:
            pass

    if MacOSFFplayAudioPlayer.is_available():
        try:
            return MacOSFFplayAudioPlayer(media_path)
        except Exception:
            pass

    return DummyAudioPlayer(media_path)
