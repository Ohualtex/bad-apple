"""
BAPB (Bad Apple Pre-rendered Binary) cache engine.

Provides zero-CPU, high-speed random-access playback of Bad Apple frames
by storing 1-bit monochrome bitmaps compressed with zlib alongside a
fast indexed lookup table.
"""

from __future__ import annotations

import os
import struct
import time
import zlib
from typing import Callable, Optional

import numpy as np

# Header specification (Total: 32 bytes)
# <4s : Magic bytes (b"BAPB")
# H   : Version (uint16)
# H   : Width (uint16)
# H   : Height (uint16)
# f   : FPS (float32)
# I   : Total frames (uint32)
# B   : Compression type (1 = zlib)
# 13s : Reserved padding
BAPB_MAGIC = b"BAPB"
BAPB_VERSION = 1
BAPB_COMPRESSION_ZLIB = 1
HEADER_STRUCT = struct.Struct("<4sHHHfIB13s")
INDEX_ENTRY_STRUCT = struct.Struct("<IH")  # offset (uint32), compressed_size (uint16)


class BinaryCacheError(Exception):
    """Base exception for binary cache errors."""

    pass


class BinaryCacheBuilder:
    """Encodes Bad Apple MP4 video frames into a high-performance BAPB binary file."""

    @staticmethod
    def build_cache(
        video_path: str,
        output_path: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
    ) -> None:
        """
        Reads Bad Apple video, thresholds frames into 1-bit bitmaps, compresses with zlib,
        and writes a structured BAPB container.
        """
        try:
            import cv2
        except ImportError:
            raise BinaryCacheError("OpenCV is required to build the binary cache.")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise BinaryCacheError(f"Unable to open source video at '{video_path}'.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames <= 0 or width <= 0 or height <= 0:
            cap.release()
            raise BinaryCacheError("Invalid video properties or empty stream.")

        # Ensure target directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        temp_output = output_path + ".tmp"
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass

        index_entries: list[tuple[int, int]] = []
        index_table_size = total_frames * INDEX_ENTRY_STRUCT.size

        start_time = time.perf_counter()

        try:
            with open(temp_output, "wb") as f:
                # 1. Write placeholder header (32 bytes)
                header_bytes = HEADER_STRUCT.pack(
                    BAPB_MAGIC,
                    BAPB_VERSION,
                    width,
                    height,
                    fps,
                    total_frames,
                    BAPB_COMPRESSION_ZLIB,
                    b"\x00" * 13,
                )
                f.write(header_bytes)

                # 2. Reserve space for index table
                f.write(b"\x00" * index_table_size)

                # 3. Process each frame and append payload
                frame_idx = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    binary = gray > 127
                    packed_bits = np.packbits(binary).tobytes()
                    compressed = zlib.compress(packed_bits, level=6)

                    offset = f.tell()
                    comp_size = len(compressed)

                    if comp_size > 65535:
                        raise BinaryCacheError(f"Frame {frame_idx} compressed size exceeds 64KB uint16 limit ({comp_size} bytes).")

                    f.write(compressed)
                    index_entries.append((offset, comp_size))
                    frame_idx += 1

                    if progress_callback:
                        progress_callback(frame_idx, total_frames, time.perf_counter() - start_time)

                cap.release()

                if frame_idx != total_frames:
                    total_frames = frame_idx
                    # Rewrite header with corrected frame count
                    f.seek(0)
                    f.write(
                        HEADER_STRUCT.pack(
                            BAPB_MAGIC,
                            BAPB_VERSION,
                            width,
                            height,
                            fps,
                            total_frames,
                            BAPB_COMPRESSION_ZLIB,
                            b"\x00" * 13,
                        )
                    )

                # 4. Seek to index table position and write entries
                f.seek(HEADER_STRUCT.size)
                index_bytes = bytearray()
                for offset, size in index_entries:
                    index_bytes.extend(INDEX_ENTRY_STRUCT.pack(offset, size))
                f.write(index_bytes)

            # Replace destination atomically
            os.replace(temp_output, output_path)
        except Exception:
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except OSError:
                    pass
            raise


class BinaryCacheReader:
    """Reads frames from a BAPB cache file with zero-CPU random access seeking."""

    def __init__(self, cache_path: str):
        if not os.path.isfile(cache_path):
            raise BinaryCacheError(f"Cache file '{cache_path}' does not exist.")

        self._file = open(cache_path, "rb")
        header_data = self._file.read(HEADER_STRUCT.size)
        if len(header_data) < HEADER_STRUCT.size:
            self.close()
            raise BinaryCacheError("Corrupted or incomplete BAPB header.")

        (
            magic,
            version,
            self.width,
            self.height,
            self.fps,
            self.total_frames,
            compression,
            _,
        ) = HEADER_STRUCT.unpack(header_data)

        if magic != BAPB_MAGIC:
            self.close()
            raise BinaryCacheError(f"Invalid magic bytes: expected {BAPB_MAGIC}, got {magic}.")
        if version != BAPB_VERSION:
            self.close()
            raise BinaryCacheError(f"Unsupported BAPB format version: {version}.")
        if compression != BAPB_COMPRESSION_ZLIB:
            self.close()
            raise BinaryCacheError(f"Unsupported compression type: {compression}.")

        self.expected_unpacked_len = self.width * self.height
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0.0

        # Read index table into numpy structured array for O(1) memory lookup
        table_bytes_len = self.total_frames * INDEX_ENTRY_STRUCT.size
        table_bytes = self._file.read(table_bytes_len)
        if len(table_bytes) < table_bytes_len:
            self.close()
            raise BinaryCacheError("Corrupted or truncated BAPB index table.")

        self._index = np.frombuffer(
            table_bytes,
            dtype=np.dtype([("offset", "<u4"), ("size", "<u2")]),
        )

    def get_frame(self, frame_idx: int) -> np.ndarray:
        """
        Reads, decompresses, and unpacks a single frame by index into a 2D boolean array (Height x Width).
        """
        if frame_idx < 0 or frame_idx >= self.total_frames:
            raise IndexError(f"Frame index {frame_idx} out of range [0, {self.total_frames - 1}].")

        offset = int(self._index["offset"][frame_idx])
        size = int(self._index["size"][frame_idx])

        self._file.seek(offset)
        compressed = self._file.read(size)
        if len(compressed) < size:
            raise BinaryCacheError(f"Truncated frame data at index {frame_idx} (expected {size} bytes, got {len(compressed)}).")
        try:
            raw = zlib.decompress(compressed)
        except zlib.error as err:
            raise BinaryCacheError(f"Corrupted frame payload at index {frame_idx}: {err}") from err

        unpacked = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))
        if len(unpacked) > self.expected_unpacked_len:
            unpacked = unpacked[: self.expected_unpacked_len]
        return unpacked.reshape((self.height, self.width))

    def close(self) -> None:
        """Closes the underlying binary file."""
        if hasattr(self, "_file") and self._file and not self._file.closed:
            self._file.close()

    def __enter__(self) -> BinaryCacheReader:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
