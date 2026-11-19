from pathlib import Path
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "P00P-1024.png"


def Main():
    App = QGuiApplication.instance() or QGuiApplication(sys.argv)
    Image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    Image.fill(QColor("#030604"))

    Painter = QPainter(Image)
    Painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    Painter.setPen(QPen(QColor("#b8ff78"), 30))
    Painter.setBrush(QColor("#071009"))
    Painter.drawRoundedRect(QRectF(44, 44, 936, 936), 96, 96)

    EmojiFont = QFont("Apple Color Emoji")
    EmojiFont.setPixelSize(500)
    Painter.setFont(EmojiFont)
    Painter.setPen(QColor("#f4f4f4"))
    Painter.drawText(QRectF(112, 90, 800, 590), Qt.AlignmentFlag.AlignCenter, "💩")

    LabelFont = QFont("Menlo")
    LabelFont.setPixelSize(170)
    LabelFont.setBold(True)
    Painter.setFont(LabelFont)
    Painter.setPen(QColor("#b8ff78"))
    Painter.drawText(QRectF(80, 690, 864, 210), Qt.AlignmentFlag.AlignCenter, "P00P")
    Painter.end()

    if not Image.save(str(OUTPUT)):
        raise RuntimeError(f"could not write {OUTPUT}")
    App.quit()


if __name__ == "__main__":
    Main()
