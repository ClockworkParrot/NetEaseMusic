# -*- coding: utf-8 -*-
"""网易云音乐下载器（仿官方 UI 重写版）入口

运行:  python3 main.py
依赖:  PyQt5 / requests / mutagen(可选) / pysocks(可选)
"""
import sys

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

from app.core.settings import AppSettings
from app.ui.theme import build_qss, LIGHT, DARK
from app.ui.icons import app_icon
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NetEaseMusicDownloader")
    app.setWindowIcon(app_icon())

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    settings = AppSettings()
    dark = bool(settings.get("dark"))
    app.setStyleSheet(build_qss(DARK if dark else LIGHT))

    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
