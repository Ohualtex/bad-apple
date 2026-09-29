import ctypes
import os


class AudioPlayer:
    """
    Built-in audio player using Windows Media Control Interface (winmm.dll / MCI)
    to play, seek, and pause MP3 audio with hardware acceleration
    without requiring external packages or child processes.
    """

    def __init__(self, media_path: str = "bad_apple.mp3"):
        self.media_path = os.path.abspath(media_path)
        self.alias = "bad_apple_audio"
        self._winmm = ctypes.windll.winmm if hasattr(ctypes, "windll") else None
        self._is_open = False
        self._is_paused = False

    def _send(self, command: str) -> int:
        if not self._winmm:
            return -1
        return self._winmm.mciSendStringW(command, None, 0, 0)

    def start(self):
        """Opens the audio file and begins playback."""
        if not os.path.exists(self.media_path) or not self._winmm:
            return

        # Close any previous instance if open
        self.stop()

        # Open file with MCI
        open_cmd = f'open "{self.media_path}" type mpegvideo alias {self.alias}'
        res = self._send(open_cmd)
        if res == 0:
            self._is_open = True
            # Set time format to milliseconds for accurate synchronization
            self._send(f"set {self.alias} time format milliseconds")
            self._send(f"play {self.alias}")
            self._is_paused = False

    def pause(self):
        """Pauses the audio."""
        if self._is_open:
            self._send(f"pause {self.alias}")
            self._is_paused = True

    def resume(self):
        """Resumes audio playback."""
        if self._is_open:
            self._send(f"resume {self.alias}")
            self._is_paused = False

    def seek(self, seconds: float):
        """Seeks to the specified position in seconds (millisecond precision)."""
        if self._is_open:
            ms = int(max(0.0, seconds) * 1000)
            self._send(f"seek {self.alias} to {ms}")
            if not self._is_paused:
                self._send(f"play {self.alias}")

    def stop(self):
        """Stops audio and releases the MCI device."""
        if self._is_open:
            self._send(f"stop {self.alias}")
            self._send(f"close {self.alias}")
            self._is_open = False

    def __del__(self):
        self.stop()
