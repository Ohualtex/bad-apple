"""
macOS-native audio player using system afplay command.
Includes CoreAudio graceful teardown to avoid terminal audio pops.
"""

import os
import shutil
import signal
import subprocess
import sys
from .base import BaseAudioPlayer


class MacAfplayAudioPlayer(BaseAudioPlayer):
    """
    Zero-dependency audio player leveraging macOS built-in afplay command.
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        super().__init__(media_path)
        if sys.platform != "darwin":
            raise RuntimeError("MacAfplayAudioPlayer is only supported on macOS.")
        if not shutil.which("afplay"):
            raise RuntimeError("afplay command not found on macOS.")
        self._proc = None

    @classmethod
    def is_available(cls) -> bool:
        """Checks if current platform is macOS and afplay is in PATH."""
        return sys.platform == "darwin" and shutil.which("afplay") is not None

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return

        self.stop()
        try:
            self._proc = subprocess.Popen(
                ["afplay", self.media_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.is_open = True
            self.is_paused = False
        except Exception:
            self._proc = None
            self.is_open = False

    def pause(self) -> None:
        if self._proc and self._proc.poll() is None and not self.is_paused:
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
                    self.is_paused = False
                except Exception:
                    pass

    def seek(self, seconds: float) -> None:
        # Native afplay does not support in-flight seeking without restart.
        # Fallback: re-spawns afplay (or user uses pygame/mpv for seeking)
        pass

    def stop(self) -> None:
        if self._proc:
            try:
                # If paused, wake up with SIGCONT before teardown
                if self.is_paused:
                    sig_cont = getattr(signal, "SIGCONT", None)
                    if sig_cont:
                        try:
                            os.kill(self._proc.pid, sig_cont)
                        except Exception:
                            pass

                # Graceful CoreAudio teardown via SIGINT
                sig_int = getattr(signal, "SIGINT", None)
                if sig_int:
                    try:
                        os.kill(self._proc.pid, sig_int)
                        self._proc.wait(timeout=0.15)
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
