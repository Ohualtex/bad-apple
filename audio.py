import ctypes
import os
import shutil
import signal
import subprocess
import sys


class AudioPlayer:
    """
    Cross-platform built-in audio player supporting:
    - Windows: Windows Media Control Interface (winmm.dll / MCI)
    - macOS: native afplay command
    - Linux: ffplay, mpv, or aplay/paplay
    Provides zero-dependency audio playback with hardware acceleration.
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        self.media_path = os.path.abspath(media_path)
        self.platform = sys.platform
        self._is_open = False
        self._is_paused = False
        self._proc = None

        # Windows MCI configuration
        self.alias = "bad_apple_audio"
        self._winmm = None
        if self.platform == "win32" and hasattr(ctypes, "windll"):
            self._winmm = getattr(ctypes.windll, "winmm", None)

        # POSIX (macOS & Linux) player discovery
        self._posix_cmd = None
        if self.platform != "win32":
            # Priority: ffplay, mpv (offer seeking, seamless pause, and zero audio crackle)
            for cmd in ["ffplay", "mpv"]:
                if shutil.which(cmd):
                    self._posix_cmd = cmd
                    break

            if not self._posix_cmd:
                if self.platform == "darwin" and shutil.which("afplay"):
                    self._posix_cmd = "afplay"
                elif self.platform.startswith("linux"):
                    for cmd in ["paplay", "aplay"]:
                        if shutil.which(cmd):
                            self._posix_cmd = cmd
                            break

    def _send_mci(self, command: str) -> int:
        if not self._winmm:
            return -1
        return self._winmm.mciSendStringW(command, None, 0, 0)

    def start(self):
        """Opens audio file and begins playback according to host OS."""
        if not os.path.exists(self.media_path):
            return

        self.stop()

        if self.platform == "win32" and self._winmm:
            open_cmd = f'open "{self.media_path}" type mpegvideo alias {self.alias}'
            res = self._send_mci(open_cmd)
            if res == 0:
                self._is_open = True
                self._send_mci(f"set {self.alias} time format milliseconds")
                self._send_mci(f"play {self.alias}")
                self._is_paused = False

        elif self.platform != "win32" and self._posix_cmd:
            try:
                cmd = [self._posix_cmd]
                if self._posix_cmd == "ffplay":
                    cmd += ["-nodisp", "-autoexit", self.media_path]
                elif self._posix_cmd == "mpv":
                    cmd += ["--no-video", self.media_path]
                else:  # afplay, paplay, aplay
                    cmd += [self.media_path]
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._is_open = True
                self._is_paused = False
            except Exception:
                self._proc = None

    def pause(self):
        """Pauses the audio."""
        if self.platform == "win32" and self._is_open:
            self._send_mci(f"pause {self.alias}")
            self._is_paused = True
        elif self.platform != "win32" and self._proc and self._proc.poll() is None and not self._is_paused:
            try:
                sig_stop = getattr(signal, "SIGSTOP", None)
                if sig_stop:
                    os.kill(self._proc.pid, sig_stop)
                self._is_paused = True
            except Exception:
                pass

    def resume(self):
        """Resumes audio playback."""
        if self.platform == "win32" and self._is_open:
            self._send_mci(f"resume {self.alias}")
            self._is_paused = False
        elif self.platform != "win32" and self._proc and self._proc.poll() is None and self._is_paused:
            try:
                sig_cont = getattr(signal, "SIGCONT", None)
                if sig_cont:
                    os.kill(self._proc.pid, sig_cont)
                self._is_paused = False
            except Exception:
                pass

    def seek(self, seconds: float):
        """Seeks to the specified position in seconds."""
        if self.platform == "win32" and self._is_open:
            ms = int(max(0.0, seconds) * 1000)
            self._send_mci(f"seek {self.alias} to {ms}")
            if not self._is_paused:
                self._send_mci(f"play {self.alias}")
        elif self.platform != "win32":
            # For POSIX backends with seeking support (ffplay, mpv)
            if self._posix_cmd in ("ffplay", "mpv"):
                self.stop()
                try:
                    cmd = [self._posix_cmd]
                    if self._posix_cmd == "ffplay":
                        cmd += ["-nodisp", "-autoexit", "-ss", str(seconds), self.media_path]
                    elif self._posix_cmd == "mpv":
                        cmd += ["--no-video", f"--start={seconds}", self.media_path]
                    self._proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._is_open = True
                    self._is_paused = False
                except Exception:
                    pass

    def stop(self):
        """Stops audio and releases resources."""
        if self.platform == "win32" and self._is_open:
            self._send_mci(f"stop {self.alias}")
            self._send_mci(f"close {self.alias}")
            self._is_open = False
            self._is_paused = False
        elif self.platform != "win32" and self._proc:
            try:
                if self._is_paused:
                    sig_cont = getattr(signal, "SIGCONT", None)
                    if sig_cont:
                        try:
                            os.kill(self._proc.pid, sig_cont)
                        except Exception:
                            pass

                # If backend is afplay, send SIGINT first for graceful CoreAudio teardown
                if self._posix_cmd == "afplay":
                    try:
                        sig_int = getattr(signal, "SIGINT", None)
                        if sig_int:
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
            self._proc = None
            self._is_open = False
            self._is_paused = False

    def __del__(self):
        self.stop()
