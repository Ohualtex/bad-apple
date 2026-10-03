import hashlib
import os
import socket
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

DEFAULT_CACHE_NAME = "bad_apple.bin"
CACHE_URLS = [
    "https://github.com/Ohualtex/bad-apple/releases/download/v1.1.2/bad_apple.bin",
    "https://github.com/Ohualtex/bad-apple/releases/download/v1.1.1/bad_apple.bin",
]
CACHE_URL = CACHE_URLS[0]
CACHE_MD5 = "bfb923d8e071539a4b23a9a9fabe6b04"


def get_media_cache_dir() -> str:
    """Returns the platform-standard persistent cache directory for Bad Apple media assets."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        cache_dir = os.path.join(base, "bad-apple")
    elif sys.platform == "darwin":
        cache_dir = os.path.expanduser("~/Library/Caches/bad-apple")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        cache_dir = os.path.join(base, "bad-apple")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_asset_path(filename: str) -> str:
    """
    Finds the asset path:
    1. If exists in current working directory, use local file.
    2. Otherwise, returns the path inside the platform cache directory.
    """
    if os.path.exists(filename):
        return filename
    return os.path.join(get_media_cache_dir(), filename)


def verify_md5(file_path: str, expected_md5: str) -> bool:
    """Verifies the MD5 digest of a file to check integrity and authenticity."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == expected_md5.lower()


def _download_file(url_or_urls: str | list[str], destination: str, expected_md5: str, label: str) -> str:
    if os.path.exists(destination):
        print(f"[*] '{destination}' ({label}) already exists. Checking integrity...")
        if verify_md5(destination, expected_md5):
            print(f"[✓] {label} integrity verified (MD5 matched).")
            return destination
        else:
            print(f"[!] Existing {label} is corrupted or incomplete, re-downloading...")
            os.remove(destination)

    urls = [url_or_urls] if isinstance(url_or_urls, str) else list(url_or_urls)

    # Guard against indefinite silent socket hangs
    socket.setdefaulttimeout(30.0)

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

    last_error: Exception | None = None
    for idx, url in enumerate(urls, 1):
        if len(urls) > 1:
            print(f"[*] Downloading {label} (source {idx}/{len(urls)}): {url}")
        else:
            print(f"[*] Downloading {label}: {url}")

        temp_destination = destination + ".tmp"
        if os.path.exists(temp_destination):
            try:
                os.remove(temp_destination)
            except OSError:
                pass

        try:
            urllib.request.urlretrieve(url, temp_destination, reporthook=ProgressHook())
            print(f"\n[✓] {label} download completed. Checking integrity...")
            if verify_md5(temp_destination, expected_md5):
                print(f"[✓] MD5 verification successful! {label} is verified.")
                os.replace(temp_destination, destination)
                return destination
            else:
                raise ValueError(f"{label} MD5 verification failed! Downloaded file may be corrupted.")
        except Exception as e:
            last_error = e
            if os.path.exists(temp_destination):
                try:
                    os.remove(temp_destination)
                except OSError:
                    pass
            print(f"\n[!] Failed to download from {url}: {e}")
            if idx < len(urls):
                print("[*] Retrying with fallback source...")

    raise RuntimeError(f"Error while downloading {label} after trying {len(urls)} source(s): {last_error}")


def download_video(destination: str | None = None) -> str:
    """Downloads the original Bad Apple video file."""
    dest = destination or get_asset_path(DEFAULT_VIDEO_NAME)
    return _download_file(VIDEO_URL, dest, VIDEO_MD5, "Bad Apple Video")


def download_audio(destination: str | None = None) -> str:
    """Downloads the original Bad Apple MP3 audio file."""
    dest = destination or get_asset_path(DEFAULT_AUDIO_NAME)
    return _download_file(AUDIO_URL, dest, AUDIO_MD5, "Bad Apple Audio")


def download_binary_cache(destination: str | None = None) -> str:
    """Downloads the pre-rendered Bad Apple BAPB binary cache file."""
    dest = destination or get_asset_path(DEFAULT_CACHE_NAME)
    return _download_file(CACHE_URLS, dest, CACHE_MD5, "Bad Apple Binary Cache")


def download_all():
    """Downloads and verifies all required media files (binary cache and audio)."""
    try:
        download_binary_cache()
    except Exception:
        download_video()
    download_audio()


if __name__ == "__main__":
    download_all()
