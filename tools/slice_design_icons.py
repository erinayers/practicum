"""Slices `design/icons.png` (the 3x3 icon sheet supplied by design) into the individual
transparent PNGs the desktop app ships in `desktop/src/practicum_desktop/assets/icons/`.

Run it again whenever the sheet changes:

    python tools/slice_design_icons.py

The sheet is a white page with nine icons laid out in a grid; the grid is located from the
blank rows/columns between them, each icon is cropped to its bounding box, and the white
page is removed with a flood fill from the outside (a plain "white = transparent" key would
also punch out the white check / cross / bang inside the coloured circles). Output is
256 px square, which Qt scales down smoothly for 14-40 px use on any DPI.

Two icons the sheet does not contain - `refresh` and `stop` - are *derived*: drawn here in the
same language as the black discs (248 px disc, 24 px white strokes with round ends, same
glyph footprint as play/back/forward) so Restart / Reload / Stop match the supplied set.
Replace them with real artwork by adding cells to the sheet and rows to NAMES.

Requires Pillow and NumPy (not runtime dependencies of the app).
"""

from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design" / "icons.png"
OUTPUT_DIR = ROOT / "desktop" / "src" / "practicum_desktop" / "assets" / "icons"
SIZE = 256

# Row-major names for the sheet's cells; the meanings are documented in
# desktop/src/practicum_desktop/icons.py (ICONS).
NAMES = (
    ("success", "error", "warning"),
    ("back", "forward", "play"),
    ("terminal", "desktop", "tools"),
)
# The coloured status icons keep their artwork as drawn (a solid disc with a white glyph).
# The others are black "ink" icons: they are stored as alpha masks - white cut-outs such
# as the arrow inside the circle become transparent - so the app can re-tint them (white on
# dark buttons, grey when disabled) and the cut-outs always show the background through.
COLOURED = {"success", "error", "warning"}


def bands(profile: np.ndarray, min_gap: int = 20) -> list[list[int]]:
    """[start, end] index ranges where `profile` is True, merging gaps under `min_gap`."""
    out: list[list[int]] = []
    start: int | None = None
    for index, value in enumerate(profile):
        if value and start is None:
            start = index
        if not value and start is not None:
            out.append([start, index - 1])
            start = None
    if start is not None:
        out.append([start, len(profile) - 1])
    merged: list[list[int]] = []
    for band in out:
        if merged and band[0] - merged[-1][1] <= min_gap:
            merged[-1][1] = band[1]
        else:
            merged.append(band)
    return merged


def outside_mask(cell: np.ndarray, white_min: int = 240) -> np.ndarray:
    """Pixels connected to the cell border through near-white pixels: the page, not the icon."""
    height, width, _ = cell.shape
    near_white = cell.min(axis=2) >= white_min
    seen = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for y in range(height):
        for x in (0, width - 1):
            if near_white[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    for x in range(width):
        for y in (0, height - 1):
            if near_white[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width and near_white[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                queue.append((ny, nx))
    return seen


def dilate(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def cut_icon(cell: np.ndarray, coloured: bool) -> Image.Image:
    if coloured:
        outside = outside_mask(cell)
        rim = dilate(outside, 2) & ~outside  # anti-aliased edge blended with the white page
        alpha = np.ones(cell.shape[:2], dtype=np.float32)
        alpha[outside] = 0.0
        alpha[rim] = np.clip(1.0 - cell.min(axis=2) / 255.0, 0, 1)[rim]
        alpha3 = alpha[..., None]
        rgb = cell.copy()
        with np.errstate(divide="ignore", invalid="ignore"):
            unmatted = (cell - (1 - alpha3) * 255.0) / np.maximum(alpha3, 1e-6)
        rgb[rim] = np.clip(unmatted[rim], 0, 255)
        rgb[outside] = 0
    else:
        # Ink mask: how dark the pixel is becomes its opacity; the colour is plain black.
        alpha = np.clip(1.0 - cell.min(axis=2) / 255.0, 0, 1)
        rgb = np.zeros_like(cell)
    rgba = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    image = Image.fromarray(rgba, "RGBA")
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


# Derived icons are drawn at this scale and downsampled for anti-aliasing.
SUPERSAMPLE = 4
DISC_RADIUS = 124  # the supplied discs are 248 px wide in a 256 px cell
STROKE = 24  # the supplied arrows' shaft thickness


def _disc_mask(draw: ImageDraw.ImageDraw) -> None:
    c, r = 128 * SUPERSAMPLE, DISC_RADIUS * SUPERSAMPLE
    draw.ellipse((c - r, c - r, c + r, c + r), fill=255)


def draw_refresh(draw: ImageDraw.ImageDraw) -> None:
    """A circular arrow (↻): a 270° ring, gap at the top, arrowhead at the clockwise end."""
    k = SUPERSAMPLE
    c = 128 * k
    ring_r = 50 * k
    width = STROKE * k
    box = (c - ring_r, c - ring_r, c + ring_r, c + ring_r)
    # PIL angles: 0° = 3 o'clock, increasing clockwise (y grows downwards). The sweep runs
    # from the top-right, down the right side, round the bottom and up the left to the
    # top-left, leaving a 90° gap centred just right of 12 o'clock for the arrowhead.
    start, end = 335, 245
    draw.arc(box, start=start, end=end, fill=0, width=width)
    sx = c + ring_r * math.cos(math.radians(start))
    sy = c + ring_r * math.sin(math.radians(start))
    draw.ellipse((sx - width / 2, sy - width / 2, sx + width / 2, sy + width / 2), fill=0)
    # Arrowhead: base across the stroke at the sweep's end, apex ahead along the tangent.
    tip = math.radians(end)
    ex = c + ring_r * math.cos(tip)
    ey = c + ring_r * math.sin(tip)
    tangent = tip + math.pi / 2  # direction of clockwise travel at the tip
    nx, ny = math.cos(tip), math.sin(tip)  # radial (outwards)
    head, half = 44 * k, 36 * k
    back = 6 * k  # let the base overlap the stroke end so there is no seam
    bx, by = ex - back * math.cos(tangent), ey - back * math.sin(tangent)
    ax, ay = ex + head * math.cos(tangent), ey + head * math.sin(tangent)
    draw.polygon(
        [(ax, ay), (bx + half * nx, by + half * ny), (bx - half * nx, by - half * ny)], fill=0
    )


def draw_stop(draw: ImageDraw.ImageDraw) -> None:
    """A rounded square, the footprint of the play triangle."""
    k = SUPERSAMPLE
    c, half, radius = 128 * k, 44 * k, 10 * k
    draw.rounded_rectangle((c - half, c - half, c + half, c + half), radius=radius, fill=0)


DERIVED = {"refresh": draw_refresh, "stop": draw_stop}


def derived_icon(name: str) -> Image.Image:
    """Black ink mask: opaque disc with the glyph cut out (same encoding as the black icons)."""
    big = 256 * SUPERSAMPLE
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    _disc_mask(draw)
    DERIVED[name](draw)
    alpha = mask.resize((SIZE, SIZE), Image.LANCZOS)
    rgba = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    rgba.putalpha(alpha)
    return rgba


def main() -> None:
    sheet = np.asarray(Image.open(SOURCE).convert("RGB")).astype(np.float32)
    ink = (255 - sheet.min(axis=2)) > 20
    row_bands = bands(ink.any(axis=1))
    col_bands = bands(ink.any(axis=0))
    if (len(row_bands), len(col_bands)) != (len(NAMES), len(NAMES[0])):
        raise SystemExit(
            f"Expected a {len(NAMES)}x{len(NAMES[0])} grid in {SOURCE}, found "
            f"{len(row_bands)}x{len(col_bands)}"
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pad = 4
    for row, (y0, y1) in enumerate(row_bands):
        for column, (x0, x1) in enumerate(col_bands):
            cell_ink = ink[y0 : y1 + 1, x0 : x1 + 1]
            ys = np.where(cell_ink.any(axis=1))[0]
            xs = np.where(cell_ink.any(axis=0))[0]
            cell = sheet[
                y0 + ys.min() - pad : y0 + ys.max() + 1 + pad,
                x0 + xs.min() - pad : x0 + xs.max() + 1 + pad,
            ]
            name = NAMES[row][column]
            target = OUTPUT_DIR / f"{name}.png"
            cut_icon(cell, name in COLOURED).save(target, optimize=True)
            print(f"{target.relative_to(ROOT)}  {target.stat().st_size} bytes")
    for name in DERIVED:
        target = OUTPUT_DIR / f"{name}.png"
        derived_icon(name).save(target, optimize=True)
        print(f"{target.relative_to(ROOT)}  {target.stat().st_size} bytes (derived)")


if __name__ == "__main__":
    main()
