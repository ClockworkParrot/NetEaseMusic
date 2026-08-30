# -*- coding: utf-8 -*-
"""左侧导航栏：官方布局（在线音乐 / 我的音乐 / 创建的歌单）"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QButtonGroup, QScrollArea, QSizePolicy)
from app.ui.icons import make_icon

_NAV_COLOR = "#8C8C8C"
_NAV_ACTIVE = "#EC4141"


class ClickableLabel(QLabel):
    """可点击的文本标签（创建的歌单条目）"""
    clicked = pyqtSignal()

    def mousePressEvent(self, ev):
        self.clicked.emit()

    def enterEvent(self, ev):
        self.setCursor(Qt.PointingHandCursor)
        super().enterEvent(ev)


class Sidebar(QWidget):
    navigate = pyqtSignal(str)           # "discover" / "downloads" / "local" / "nowplaying"
    playlist_clicked = pyqtSignal(str)   # 歌单 id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(208)
        self._items = {}       # key -> (btn, icon)
        self._pl_labels = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 12)
        lay.setSpacing(0)

        # ---- 在线音乐 ----
        lay.addWidget(self._section("在线音乐"))
        self._nav(lay, "discover", "发现音乐", "compass", True)
        self._nav(lay, "nowplaying", "正在播放", "note", True)

        # ---- 我的音乐 ----
        lay.addWidget(self._section("我的音乐"))
        self._nav(lay, "local", "本地音乐", "folder", True)
        self._nav(lay, "downloads", "下载管理", "download", True)

        # ---- 创建的歌单（动态） ----
        lay.addWidget(self._section("创建的歌单"))
        self._pl_area = QVBoxLayout()
        self._pl_area.setContentsMargins(0, 0, 0, 0)
        self._pl_area.setSpacing(1)
        holder = QWidget()
        holder.setLayout(self._pl_area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(holder)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        lay.addWidget(scroll, 1)
        lay.addStretch(0)

    # ---------- 构建 ----------
    def _section(self, text):
        s = QLabel(text)
        s.setObjectName("SectionLabel")
        return s

    def _nav(self, lay, key, text, icon, checkable):
        btn = QPushButton("  " + text)
        btn.setObjectName("NavItem")
        btn.setCheckable(checkable)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIcon(make_icon(icon, _NAV_COLOR, 17))
        btn.clicked.connect(lambda checked: self._on_nav(key))
        if checkable:
            btn.toggled.connect(lambda on: btn.setIcon(
                make_icon(icon, _NAV_ACTIVE if on else _NAV_COLOR, 17)))
        lay.addWidget(btn)
        self._items[key] = btn
        return btn

    def _on_nav(self, key):
        self.navigate.emit(key)

    # ---------- 状态 ----------
    def set_checked(self, key):
        """程序化选中导航项（不触发信号）"""
        btn = self._items.get(key)
        if btn:
            btn.setChecked(True)

    def set_playlists(self, playlists):
        """刷新“创建的歌单”列表：playlists = [(id, title), ...]"""
        for lb in self._pl_labels:
            self._pl_area.removeWidget(lb)
            lb.deleteLater()
        self._pl_labels = []
        for pid, title in playlists:
            lb = ClickableLabel(title)
            lb.setObjectName("SideItem")
            lb.setToolTip(title)
            lb.clicked.connect(lambda checked=False, i=pid: self.playlist_clicked.emit(i))
            self._pl_area.addWidget(lb)
            self._pl_labels.append(lb)
        if not self._pl_labels:
            hint = QLabel("  解析歌单后显示在这里")
            hint.setObjectName("SideItem")
            hint.setEnabled(False)
            self._pl_area.addWidget(hint)
            self._pl_labels.append(hint)
