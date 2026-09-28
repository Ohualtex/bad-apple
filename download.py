import hashlib
import os
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VIDEO_URL = "https://archive.org/download/niconico-sm8628149/sm8628149.mp4"
VIDEO_MD5 = "187d905116db5e217338da08a67d1caf"
DEFAULT_VIDEO_NAME = "bad_apple.mp4"

AUDIO_URL = "https://raw.githubusercontent.com/reimunyancat/badapple-with-ascii/master/bad_apple.mp3"
AUDIO_MD5 = "fd4c1a0b0ead09b5c0ab58e4b1016317"
DEFAULT_AUDIO_NAME = "bad_apple.mp3"


def verify_md5(file_path: str, expected_md5: str) -> bool:
    """Verifies the MD5 digest of a file to check integrity and authenticity."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == expected_md5.lower()


def _download_file(url: str, destination: str, expected_md5: str, label: str) -> str:
    if os.path.exists(destination):
        print(f"[*] '{destination}' ({label}) already exists. Checking integrity...")
        if verify_md5(destination, expected_md5):
            print(f"[✓] {label} integrity verified (MD5 matched).")
            return destination
        else:
            print(f"[!] Existing {label} is corrupted or incomplete, re-downloading...")
            os.remove(destination)

    print(f"[*] Downloading {label}: {url}")

    class ProgressHook:
        def __init__(self):
            self.last_percent = -1

        def __call__(self, block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, int(downloaded * 100 / total_size))
                if percent != self.last_percent:
                    self.last_percent = percent
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    bar = "=" * (percent // 2) + "-" * (50 - percent // 2)
                    sys.stdout.write(f"\r[{bar}] {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)")
                    sys.stdout.flush()

    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
    urllib.request.install_opener(opener)

    try:
        urllib.request.urlretrieve(url, destination, reporthook=ProgressHook())
        print(f"\n[✓] {label} download completed. Checking integrity...")
        if verify_md5(destination, expected_md5):
            print(f"[✓] MD5 verification successful! {label} is verified.")
            return destination
        else:
            raise ValueError(f"{label} MD5 verification failed! Downloaded file may be corrupted.")
    except Exception as e:
        if os.path.exists(destination):
            os.remove(destination)
        raise RuntimeError(f"Error while downloading {label}: {e}")


def download_video(destination: str = DEFAULT_VIDEO_NAME) -> str:
    """Downloads the original Bad Apple video file."""
    return _download_file(VIDEO_URL, destination, VIDEO_MD5, "Bad Apple Video")


def download_audio(destination: str = DEFAULT_AUDIO_NAME) -> str:
    """Downloads the original Bad Apple MP3 audio file."""
    return _download_file(AUDIO_URL, destination, AUDIO_MD5, "Bad Apple Audio")


def download_all():
    """Downloads and verifies all required media files (video and audio)."""
    download_video()
    download_audio()


if __name__ == "__main__":
    download_all()
