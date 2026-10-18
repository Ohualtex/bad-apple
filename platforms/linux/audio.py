"""
Linux-specific audio engines: Pygame mixer and multi-tiered Linux CLI audio cascade.
"""

import os
import shutil
import signal
import subprocess
import time
from ..base import BaseAudioPlayer, DummyAudioPlayer


class LinuxPygameAudioPlayer(BaseAudioPlayer):
    """
    High-precision audio playback via pygame.mixer on Linux.
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


class LinuxCliAudioPlayer(BaseAudioPlayer):
    """
    Fallback audio player supporting multiple Linux CLI backends:
    paplay (PulseAudio), pw-play (PipeWire), aplay (ALSA), ffplay, or mpv.
    Uses SIGSTOP/SIGCONT for zero-CPU pause and resume.
    """

    SUPPORTED_BINARIES = ["paplay", "pw-play", "ffplay", "mpv", "aplay"]

    def __init__(self, media_path: str = "", binary: str = "ffplay"):
        super().__init__(media_path)
        self.binary = binary
        self._proc: subprocess.Popen | None = None
        self._start_perf: float = 0.0
        self._seek_offset: float = 0.0
        self._paused_pos: float = 0.0

    @classmethod
    def find_available_binary(cls) -> str | None:
        for b in cls.SUPPORTED_BINARIES:
            if shutil.which(b) is not None:
                return b
        return None

    def _build_command(self, start_sec: float = 0.0) -> list[str]:
        if self.binary == "ffplay":
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
            if start_sec > 0:
                cmd.extend(["-ss", f"{start_sec:.3f}"])
            cmd.append(self.media_path)
            return cmd
        elif self.binary == "mpv":
            cmd = ["mpv", "--no-video", "--really-quiet"]
            if start_sec > 0:
                cmd.extend([f"--start={start_sec:.3f}"])
            cmd.append(self.media_path)
            return cmd
        else:
            # paplay, pw-play, aplay
            return [self.binary, self.media_path]

    def _spawn(self, start_sec: float = 0.0) -> None:
        self._teardown_proc()
        cmd = self._build_command(start_sec)

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


def create_linux_audio_player(media_path: str = "") -> BaseAudioPlayer:
    """
    Instantiates the optimal audio player for Linux:
    1. LinuxPygameAudioPlayer (if pygame is installed)
    2. LinuxCliAudioPlayer (via paplay, pw-play, ffplay, mpv, aplay)
    3. DummyAudioPlayer (fallback)
    """
    if LinuxPygameAudioPlayer.is_available():
        try:
            return LinuxPygameAudioPlayer(media_path)
        except Exception:
            pass

    cli_bin = LinuxCliAudioPlayer.find_available_binary()
    if cli_bin is not None:
        try:
            return LinuxCliAudioPlayer(media_path, binary=cli_bin)
        except Exception:
            pass

    return DummyAudioPlayer(media_path)
