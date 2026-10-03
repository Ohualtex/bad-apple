"""
Linux audio player using subprocess to call ffplay, mpv, paplay, or aplay.
Supports seeking when ffplay or mpv is installed.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from .base import BaseAudioPlayer


class LinuxAudioPlayer(BaseAudioPlayer):
    """
    Subprocess-based audio player for Linux and POSIX distributions (supporting ffplay, mpv, etc.).
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        super().__init__(media_path)
        self._cmd = self.detect_command()
        if not self._cmd:
            raise RuntimeError("No supported Linux/POSIX audio player command found (ffplay, mpv, paplay, aplay).")
        self._proc = None
        self._start_perf = 0.0
        self._seek_offset = 0.0
        self._paused_pos = 0.0

    @classmethod
    def detect_command(cls) -> str | None:
        """Detects available audio player executable on Linux/POSIX, ordered by feature richness."""
        for cmd in ["ffplay", "mpv", "paplay", "aplay"]:
            if shutil.which(cmd):
                return cmd
        return None

    @classmethod
    def is_available(cls) -> bool:
        """Checks if current platform is POSIX (Linux/macOS) and at least one player binary exists."""
        if sys.platform == "win32":
            return False
        return cls.detect_command() is not None

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return

        self.stop()
        try:
            cmd = [self._cmd]
            if self._cmd == "ffplay":
                cmd += ["-nodisp", "-autoexit", self.media_path]
            elif self._cmd == "mpv":
                cmd += ["--no-video", self.media_path]
            else:  # paplay, aplay
                cmd += [self.media_path]

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._start_perf = time.perf_counter()
            self._seek_offset = 0.0
            self._paused_pos = 0.0
            self.is_open = True
            self.is_paused = False
        except Exception:
            self._proc = None
            self.is_open = False

    def pause(self) -> None:
        if self._proc and self._proc.poll() is None and not self.is_paused:
            self._paused_pos = self.get_time() or 0.0
            sig_stop = getattr(signal, "SIGSTOP", None)
            if sig_stop:
                try:
                    os.kill(self._proc.pid, sig_stop)
                    self.is_paused = True
                except Exception:
                    pass

    def resume(self) -> None:
        if self._proc and self._proc.poll() is None and self.is_paused:
            sig_cont = getattr(signal, "SIGCONT", None)
            if sig_cont:
                try:
                    os.kill(self._proc.pid, sig_cont)
                    self._start_perf = time.perf_counter() - (self._paused_pos - self._seek_offset)
                    self.is_paused = False
                except Exception:
                    pass

    def seek(self, seconds: float) -> None:
        if self._cmd in ("ffplay", "mpv"):
            was_paused = self.is_paused
            self.stop()
            try:
                target_sec = max(0.0, float(seconds))
                cmd = [self._cmd]
                if self._cmd == "ffplay":
                    cmd += ["-nodisp", "-autoexit", "-ss", str(target_sec), self.media_path]
                elif self._cmd == "mpv":
                    cmd += ["--no-video", f"--start={target_sec}", self.media_path]
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._seek_offset = target_sec
                self._start_perf = time.perf_counter()
                self._paused_pos = target_sec
                self.is_open = True
                self.is_paused = False
                if was_paused:
                    self.pause()
            except Exception:
                pass

    def get_time(self) -> float | None:
        """Returns current playback position in seconds with millisecond precision."""
        if not self.is_open or not self._proc or self._proc.poll() is not None:
            return None
        if self.is_paused:
            return self._paused_pos
        elapsed = time.perf_counter() - self._start_perf
        return self._seek_offset + elapsed

    def stop(self) -> None:
        if self._proc:
            try:
                if self.is_paused:
                    sig_cont = getattr(signal, "SIGCONT", None)
                    if sig_cont:
                        try:
                            os.kill(self._proc.pid, sig_cont)
                        except Exception:
                            pass
                if self._proc.poll() is None:
                    self._proc.terminate()
                    self._proc.wait(timeout=0.2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None
                self.is_open = False
                self.is_paused = False
