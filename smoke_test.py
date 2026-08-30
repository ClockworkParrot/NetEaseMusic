# -*- coding: utf-8 -*-
"""冒烟测试：offscreen 构建主窗口、渲染全部图标、双主题 QSS"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from app.core.settings import AppSettings
from app.ui.theme import build_qss, LIGHT, DARK
from app.ui.icons import _ICONS, make_icon, make_pixmap, rounded_pixmap, app_icon
from app.ui.main_window import MainWindow

app = QApplication(sys.argv)
app.setStyleSheet(build_qss(LIGHT))

# 图标渲染检查
for name in _ICONS:
    make_icon(name, "#EC4141", 18)
make_pixmap("note", "#FFF", 40)
rounded_pixmap(None, 8)
app_icon()
print("icons ok:", len(_ICONS))

# 主窗口构建
w = MainWindow(AppSettings())
w.show()
w.resize(1160, 760)

# 深色 QSS 也检查一遍
app.setStyleSheet(build_qss(DARK))
app.setStyleSheet(build_qss(LIGHT))

QTimer.singleShot(600, app.quit)
app.exec_()
print("SMOKE OK")
