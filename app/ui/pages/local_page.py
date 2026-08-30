# -*- coding: utf-8 -*-
"""本地音乐页：目录选择 + 本地曲库表格（识别标签/时长/本地 .lrc 字幕）"""
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit, QTableWidget,
                             QTableWidgetItem, QMenu, QFileDialog)
from PyQt5.QtCore import QUrl
from app.ui.icons import make_icon

_WHITE = "#FFFFFF"
_GRAY = "#8C8C8C"


class LocalPage(QWidget):
    play_requested = pyqtSignal(list, int)     # (tracks, row) 双击/菜单播放
    play_all_requested = pyqtSignal(list)
    lrc_requested = pyqtSignal(object)         # 单曲获取/下载歌词
    dir_changed = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.tracks = []            # 全量
        self._shown = []            # 过滤后
        self._dir = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        # ---- 标题 ----
        head = QHBoxLayout()
        title = QLabel("本地音乐")
        title.setObjectName("PlaylistTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("PlaylistMeta")
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(self.count_label)
        head.addStretch(1)
        outer.addLayout(head)

        # ---- 工具行 ----
        tools = QHBoxLayout()
        tools.setSpacing(8)

        self.dir_btn = QPushButton("  选择目录")
        self.dir_btn.setObjectName("Secondary")
        self.dir_btn.setIcon(make_icon("folder", "#5C5C5C", 14))
        self.dir_btn.setCursor(Qt.PointingHandCursor)
        self.dir_btn.clicked.connect(self._pick_dir)
        tools.addWidget(self.dir_btn)

        self.refresh_btn = QPushButton("  刷新")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.setIcon(make_icon("refresh", "#5C5C5C", 14))
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        tools.addWidget(self.refresh_btn)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("过滤：歌名 / 歌手 / 专辑")
        self.filter.setFixedWidth(220)
        self.filter.textChanged.connect(self._apply_filter)
        tools.addWidget(self.filter)
        tools.addStretch(1)

        self.lrc_btn = QPushButton("  获取歌词")
        self.lrc_btn.setObjectName("Secondary")
        self.lrc_btn.setIcon(make_icon("lyrics", "#5C5C5C", 14))
        self.lrc_btn.setCursor(Qt.PointingHandCursor)
        self.lrc_btn.setToolTip("为选中的本地歌曲从网易云匹配并下载 .lrc 字幕")
        self.lrc_btn.clicked.connect(self._on_lrc)
        tools.addWidget(self.lrc_btn)

        play_all = QPushButton("  播放全部")
        play_all.setObjectName("Primary")
        play_all.setIcon(make_icon("play", _WHITE, 13))
        play_all.setCursor(Qt.PointingHandCursor)
        play_all.clicked.connect(lambda: self.play_all_requested.emit(list(self._shown)))
        tools.addWidget(play_all)
        outer.addLayout(tools)

        # ---- 曲库表 ----
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("SongTableWidget")
        self.table.setHorizontalHeaderLabels(
            ["#", "标题", "歌手", "专辑", "时长", "字幕"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._on_double)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        for col, w in ((0, 44), (1, 300), (2, 180), (3, 200), (4, 70), (5, 70)):
            self.table.setColumnWidth(col, w)
        outer.addWidget(self.table, 1)

        self.empty_hint = QLabel("选择一个目录扫描本地音乐（支持 mp3 / flac / m4a / wav / ogg / ape / wma）")
        self.empty_hint.setObjectName("PlaylistMeta")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.empty_hint)

    # ---------- 数据 ----------
    def set_dir(self, d):
        self._dir = d

    def set_tracks(self, tracks):
        self.tracks = list(tracks)
        self._apply_filter()

    def refresh_lrc_state(self, path):
        """获取歌词后刷新该行的字幕列"""
        for row, t in enumerate(self._shown):
            if t.path == path:
                self._set_lrc_cell(row, t.has_lrc)
                return

    def _apply_filter(self):
        kw = self.filter.text().strip().lower()
        if kw:
            self._shown = [t for t in self.tracks if kw in t.title.lower()
                           or kw in t.artist.lower() or kw in t.album.lower()]
        else:
            self._shown = list(self.tracks)
        tb = self.table
        tb.setRowCount(len(self._shown))
        for row, t in enumerate(self._shown):
            tb.setItem(row, 0, self._item(str(row + 1), _GRAY, align=Qt.AlignCenter))
            it = self._item(t.title)
            it.setData(Qt.UserRole, t.path)
            tb.setItem(row, 1, it)
            tb.setItem(row, 2, self._item(t.artist or "未知歌手"))
            tb.setItem(row, 3, self._item(t.album or ""))
            tb.setItem(row, 4, self._item(t.duration_text, _GRAY, align=Qt.AlignCenter))
            self._set_lrc_cell(row, t.has_lrc)
        self.count_label.setText(f"共 {len(self._shown)} 首")
        self.empty_hint.setVisible(not self._shown)

    @staticmethod
    def _item(text, color=None, align=None):
        it = QTableWidgetItem(text)
        if color:
            it.setForeground(Qt.gray)
        if align:
            it.setTextAlignment(align | Qt.AlignVCenter)
        return it

    def _set_lrc_cell(self, row, has):
        it = QTableWidgetItem("有" if has else "无")
        it.setForeground(Qt.darkGreen if has else Qt.gray)
        it.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 5, it)

    # ---------- 交互 ----------
    def _selected_track(self):
        idx = self.table.currentRow()
        if 0 <= idx < len(self._shown):
            return self._shown[idx]
        return None

    def _on_double(self, index):
        if 0 <= index.row() < len(self._shown):
            self.play_requested.emit(list(self._shown), index.row())

    def _on_lrc(self):
        t = self._selected_track()
        if t:
            self.lrc_requested.emit(t)
        else:
            self.count_label.setText("先在表格中选中一首歌")

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if not (0 <= row < len(self._shown)):
            return
        t = self._shown[row]
        menu = QMenu(self)
        a_play = menu.addAction("播放")
        a_lrc = menu.addAction("获取歌词（下载字幕）")
        a_open = menu.addAction("打开所在文件夹")
        act = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if act == a_play:
            self.play_requested.emit(list(self._shown), row)
        elif act == a_lrc:
            self.lrc_requested.emit(t)
        elif act == a_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(t.path).parent)))

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择音乐目录", str(getattr(self, "_dir", "") or ""))
        if d:
            self._dir = d
            self.dir_changed.emit(d)
