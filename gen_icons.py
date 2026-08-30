# -*- coding: utf-8 -*-
"""生成打包用图标：packaging/icon.png (256) + packaging/icon.ico"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter

from app.ui.icons import _APP_ICON_SVG
from PyQt5.QtSvg import QSvgRenderer

app = QApplication(sys.argv)
os.makedirs("packaging", exist_ok=True)


def render(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    QSvgRenderer(_APP_ICON_SVG.encode()).render(p, QRectF(0, 0, size, size))
    p.end()
    return img


render(256).save("packaging/icon.png", "PNG")
render(256).save("packaging/icon.ico", "ICO")
render(128).save("packaging/icon-128.png", "PNG")
print("icons written:", os.listdir("packaging"))
