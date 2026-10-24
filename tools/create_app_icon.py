from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "practicum.svg"
OUTPUT = ROOT / "assets" / "practicum.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_for_size(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(QByteArray(buffer.data()))


def main() -> None:
    _app = QGuiApplication([])
    renderer = QSvgRenderer(str(SOURCE))
    if not renderer.isValid():
        raise RuntimeError(f"Could not read app icon SVG: {SOURCE}")

    images = [png_for_size(renderer, size) for size in SIZES]
    header_size = 6 + 16 * len(images)
    entries = []
    offset = header_size
    for size, png in zip(SIZES, images, strict=True):
        entries.append(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,
                0,
                1,
                32,
                len(png),
                offset,
            )
        )
        offset += len(png)

    OUTPUT.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(images))
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    main()
