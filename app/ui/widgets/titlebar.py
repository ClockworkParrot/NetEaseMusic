# -*- coding: utf-8 -*-
"""顶部栏：Logo + 前进后退 + 搜索框 + 主题/设置"""
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QToolButton, QMenu
from app.ui.icons import make_icon, make_pixmap

_GRAY = "#8C8C8C"
_RED = "#EC4141"


class TitleBar(QWidget):
    search_submitted = pyqtSignal(str)
    back_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    theme_toggled = pyqtSignal()
    cookie_requested = pyqtSignal()
    proxy_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(56)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)

        # Logo
        logo = QLabel()
        logo.setPixmap(make_pixmap("note", _RED, 26))
        lay.addWidget(logo)
        name = QLabel("网易云音乐")
        name.setObjectName("LogoText")
        lay.addWidget(name)
        badge = QLabel("DOWNLOADER")
        badge.setObjectName("LogoBadge")
        lay.addWidget(badge)
        lay.addSpacing(10)

        # 前进 / 后退（视觉占位，官方样式）
        self.back_btn = self._icon_btn("back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        self.fwd_btn = self._icon_btn("forward")
        self.fwd_btn.clicked.connect(self.forward_clicked.emit)
        self.back_btn.setEnabled(False)
        self.fwd_btn.setEnabled(False)
        lay.addWidget(self.back_btn)
        lay.addWidget(self.fwd_btn)

        lay.addStretch(1)

        # 搜索框
        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("搜索歌曲 / 粘贴歌单、专辑、单曲链接")
        self.search.setFixedWidth(360)
        self.search.setClearButtonEnabled(True)
        self.search.addAction(make_icon("search", _GRAY, 15), QLineEdit.LeadingPosition)
        self.search.returnPressed.connect(lambda: self.search_submitted.emit(self.search.text().strip()))
        lay.addWidget(self.search)

        lay.addStretch(1)

        # 主题切换
        self.theme_btn = self._icon_btn("moon")
        self.theme_btn.setToolTip("切换深浅主题")
        self.theme_btn.clicked.connect(self.theme_toggled.emit)
        lay.addWidget(self.theme_btn)

        # 设置菜单
        self.settings_btn = self._icon_btn("settings")
        self.settings_btn.setToolTip("设置")
        menu = QMenu(self.settings_btn)
        menu.addAction("Cookie 设置", self.cookie_requested.emit)
        menu.addAction("网络代理设置", self.proxy_requested.emit)
        self.settings_btn.setMenu(menu)
        # 默认 DelayedPopup 需要“长按”才出菜单，单击无反应；改为点击立即弹出
        self.settings_btn.setPopupMode(QToolButton.InstantPopup)
        lay.addWidget(self.settings_btn)

    def _icon_btn(self, icon, size=34):
        b = QToolButton()
        b.setObjectName("IconButton")
        b.setIcon(make_icon(icon, _GRAY, 18))
        b.setFixedSize(size, size)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def set_dark(self, dark):
        """深色主题显示太阳（点回浅色），浅色显示月亮"""
        self.theme_btn.setIcon(make_icon("sun" if dark else "moon", _GRAY, 18))
