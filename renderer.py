import shutil
import cv2
import numpy as np

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

    MODES = ["halfblock", "ascii", "braille"]

    def __init__(self, mode: str = "halfblock", target_width: int = None, target_height: int = None):
        self.mode = mode if mode in self.MODES else "halfblock"
        self.target_width = target_width
        self.target_height = target_height

    def get_dimensions(self) -> tuple[int, int, int, int]:
        """
        Calculates character width, height, and margins (padding) to render,
        preserving the 4:3 aspect ratio based on terminal dimensions.
        """
        cols, lines = shutil.get_terminal_size(fallback=(80, 24))
        # Leave 2 lines for status bar and safe margin, and 2 columns to prevent auto-wrap
        avail_w = self.target_width or max(20, cols - 2)
        avail_h = self.target_height or max(10, lines - 2)

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
        pad_y = max(0, (avail_h - char_h) // 2)
        return char_w, char_h, pad_x, pad_y

    def render_frame(self, frame_bgr: np.ndarray) -> str:
        """
        Converts an OpenCV BGR frame into a terminal string according to the selected mode.
        """
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        char_w, char_h, pad_x, pad_y = self.get_dimensions()
        indent = " " * pad_x

        if self.mode == "halfblock":
            pixel_w = char_w
            pixel_h = char_h * 2
            resized = cv2.resize(gray, (pixel_w, pixel_h), interpolation=cv2.INTER_AREA)
            binary = (resized > 127).astype(np.uint8)

            top = binary[0::2, :]
            bottom = binary[1::2, :]
            idx = top * 2 + bottom
            char_matrix = HALF_BLOCK_LUT[idx]

        elif self.mode == "braille":
            pixel_w = char_w * 2
            pixel_h = char_h * 4
            resized = cv2.resize(gray, (pixel_w, pixel_h), interpolation=cv2.INTER_AREA)
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
            resized = cv2.resize(gray, (char_w, char_h), interpolation=cv2.INTER_AREA)
            idx = (resized.astype(np.float32) / 256.0 * len(ASCII_CHARS)).astype(np.int32)
            idx = np.clip(idx, 0, len(ASCII_CHARS) - 1)
            char_matrix = ASCII_CHARS[idx]

        rendered_lines = [indent + "".join(row) for row in char_matrix]
        vertical_pad = [""] * pad_y
        return "\n".join(vertical_pad + rendered_lines)
