import shutil
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

# Half blocks: Combinations of top and bottom pixels
HALF_BLOCK_LUT = np.array([" ", "▄", "▀", "█"], dtype="<U1")

# Classic ASCII character gradient
ASCII_CHARS = np.array(list(" .:-=+*#%@"), dtype="<U1")

# Braille 2x4 pixel matrix (0x2800 - 0x28FF)
BRAILLE_LUT = np.array([chr(0x2800 + i) for i in range(256)], dtype="<U1")


class TerminalRenderer:
    """
    High-performance rendering engine that converts frames into terminal characters
    (Half Block, ASCII, Braille) and centers them on screen.
    """

    MODES = ["ascii", "braille", "halfblock"]

    def __init__(self, mode: str = "ascii", target_width: int = None, target_height: int = None):
        self.mode = mode if mode in self.MODES else "ascii"
        self.target_width = target_width
        self.target_height = target_height
        self._grid_key = None
        self._y0 = None
        self._y1 = None
        self._x0 = None
        self._x1 = None
        self._areas = None
        self._cum = None

    def get_dimensions(self) -> tuple[int, int, int, int, int]:
        """
        Calculates character width, height, and margins (padding) to render,
        preserving the 4:3 aspect ratio based on terminal dimensions.
        """
        cols, lines = shutil.get_terminal_size(fallback=(80, 24))
        # Leave 3 lines for status bar, blank line separator and safe margin, and 2 columns to prevent auto-wrap
        avail_w = max(4, self.target_width) if self.target_width is not None else max(4, cols - 2)
        avail_h = max(2, self.target_height) if self.target_height is not None else max(2, lines - 3)

        # Bad Apple original aspect ratio: 4:3 (1.333)
        # Terminal character cell ratio is typically ~1:2 (height is ~2x width).
        if self.mode == "halfblock":
            # 1 character cell has 2 vertical pixels.
            # Thus 1 char width = 1 pixel width; 1 char height = 2 pixel height.
            # Since character cells have a ~1:2 ratio, half blocks produce nearly square pixels!
            # For 4:3 video aspect ratio: char_h = char_w * (3/4) / 2 = char_w * 3 / 8
            w_by_h = int(avail_h * 8 / 3)
            h_by_w = int(avail_w * 3 / 8)
            if h_by_w <= avail_h:
                char_w = avail_w
                char_h = h_by_w
            else:
                char_w = w_by_h
                char_h = avail_h
        elif self.mode == "braille":
            # A Braille cell contains 2 columns x 4 rows of pixels.
            # char_h = char_w * (3/4) * (2/4) = char_w * 3 / 8
            w_by_h = int(avail_h * 8 / 3)
            h_by_w = int(avail_w * 3 / 8)
            if h_by_w <= avail_h:
                char_w = avail_w
                char_h = h_by_w
            else:
                char_w = w_by_h
                char_h = avail_h
        else:  # ascii
            # In standard ASCII, 1 character = 1 pixel.
            # Height is 2x, so: char_h = char_w * (3/4) * 0.5 = char_w * 3 / 8
            w_by_h = int(avail_h * 8 / 3)
            h_by_w = int(avail_w * 3 / 8)
            if h_by_w <= avail_h:
                char_w = avail_w
                char_h = h_by_w
            else:
                char_w = w_by_h
                char_h = avail_h

        char_w = max(4, char_w)
        char_h = max(2, char_h)

        pad_x = max(0, (cols - char_w) // 2)
        pad_top = max(0, (avail_h - char_h) // 2)
        pad_bottom = max(0, avail_h - char_h - pad_top)
        return char_w, char_h, pad_x, pad_top, pad_bottom

    def _resize(self, gray: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """Resizes grayscale/binary matrix using cv2.INTER_AREA or fast pure-NumPy box filter downsampling."""
        if cv2 is not None:
            return cv2.resize(gray, (target_w, target_h), interpolation=cv2.INTER_AREA)

        h, w = gray.shape
        # Fallback to nearest-neighbor if upsampling
        if target_w >= w or target_h >= h:
            row_idx = np.linspace(0, h - 1, target_h).astype(np.int32)
            col_idx = np.linspace(0, w - 1, target_w).astype(np.int32)
            return gray[row_idx[:, None], col_idx]

        # Area averaging via 2D summed-area table (integral image)
        grid_key = (h, w, target_w, target_h)
        if self._grid_key != grid_key:
            y_edges = np.round(np.linspace(0, h, target_h + 1)).astype(np.int32)
            x_edges = np.round(np.linspace(0, w, target_w + 1)).astype(np.int32)
            self._y0 = y_edges[:-1, None]
            self._y1 = y_edges[1:, None]
            self._x0 = x_edges[None, :-1]
            self._x1 = x_edges[None, 1:]
            self._areas = np.maximum((self._y1 - self._y0) * (self._x1 - self._x0), 1).astype(np.float32)
            self._cum = np.zeros((h + 1, w + 1), dtype=np.uint32)
            self._grid_key = grid_key

        np.cumsum(gray, axis=0, dtype=np.uint32, out=self._cum[1:, 1:])
        np.cumsum(self._cum[1:, 1:], axis=1, dtype=np.uint32, out=self._cum[1:, 1:])

        sums = (
            self._cum[self._y1, self._x1]
            - self._cum[self._y0, self._x1]
            - self._cum[self._y1, self._x0]
            + self._cum[self._y0, self._x0]
        )
        return (sums / self._areas).astype(np.uint8)

    def render_frame(self, frame_bgr: np.ndarray) -> str:
        """
        Converts an OpenCV BGR frame into a terminal string according to the selected mode.
        """
        if cv2 is not None:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = np.dot(frame_bgr[..., :3], [0.114, 0.587, 0.299]).astype(np.uint8)
        return self._render_core(gray)

    def render_binary_frame(self, binary_matrix: np.ndarray) -> str:
        """
        Converts a 1-bit boolean or uint8 binary frame directly into a terminal string.
        Skips BGR to grayscale conversion for zero-overhead binary cache playback.
        """
        if binary_matrix.dtype == bool:
            gray = binary_matrix.astype(np.uint8) * 255
        elif binary_matrix.dtype == np.uint8:
            gray = (binary_matrix > 0).astype(np.uint8) * 255
        else:
            gray = binary_matrix
        return self._render_core(gray)

    def _render_core(self, gray: np.ndarray) -> str:
        """Internal core that maps a 2D grayscale/binary image to terminal characters."""
        char_w, char_h, pad_x, pad_top, pad_bottom = self.get_dimensions()
        indent = " " * pad_x

        if self.mode == "halfblock":
            pixel_w = char_w
            pixel_h = char_h * 2
            resized = self._resize(gray, pixel_w, pixel_h)
            binary = (resized > 127).astype(np.uint8)

            top = binary[0::2, :]
            bottom = binary[1::2, :]
            idx = top * 2 + bottom
            char_matrix = HALF_BLOCK_LUT[idx]

        elif self.mode == "braille":
            pixel_w = char_w * 2
            pixel_h = char_h * 4
            resized = self._resize(gray, pixel_w, pixel_h)
            binary = (resized > 127).astype(np.uint16)

            d1 = binary[0::4, 0::2]
            d2 = binary[1::4, 0::2] * 2
            d3 = binary[2::4, 0::2] * 4
            d4 = binary[0::4, 1::2] * 8
            d5 = binary[1::4, 1::2] * 16
            d6 = binary[2::4, 1::2] * 32
            d7 = binary[3::4, 0::2] * 64
            d8 = binary[3::4, 1::2] * 128

            pattern = d1 + d2 + d3 + d4 + d5 + d6 + d7 + d8
            char_matrix = BRAILLE_LUT[pattern]

        else:  # ascii
            resized = self._resize(gray, char_w, char_h)
            idx = (resized.astype(np.float32) / 256.0 * len(ASCII_CHARS)).astype(np.int32)
            idx = np.clip(idx, 0, len(ASCII_CHARS) - 1)
            char_matrix = ASCII_CHARS[idx]

        rendered_lines = [indent + "".join(row) + "\033[K" for row in char_matrix]
        top_pad = ["\033[K"] * pad_top
        bottom_pad = ["\033[K"] * pad_bottom
        return "\n".join(top_pad + rendered_lines + bottom_pad)
