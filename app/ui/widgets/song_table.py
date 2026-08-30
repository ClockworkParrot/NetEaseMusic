# -*- coding: utf-8 -*-
"""歌曲表格：发现页搜索结果 / 歌单详情共用"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

_GRAY = "#8C8C8C"
_RED = "#EC4141"

COLUMNS = ["#", "歌曲", "歌手", "专辑", "时长"]


class SongTable(QTableWidget):
    play_requested = pyqtSignal(object, int)   # Song, 行号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels(COLUMNS)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(42)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Fixed)
        self.setColumnWidth(0, 52)
        self.setColumnWidth(3, 220)
        self.setColumnWidth(4, 70)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setStretchLastSection(False)

        self.doubleClicked.connect(self._on_double)
        self._songs = []
        self._playing_id = ""

    # ---------- 数据 ----------
    def set_songs(self, songs):
        self._songs = list(songs)
        self._playing_id = ""
        self.setRowCount(len(self._songs))
        for row, s in enumerate(self._songs):
            self._fill_row(row)

    def songs(self):
        return list(self._songs)

    def selected_songs(self):
        rows = sorted({i.row() for i in self.selectedIndexes()})
        return [self._songs[r] for r in rows if 0 <= r < len(self._songs)]

    def song_at(self, row):
        if 0 <= row < len(self._songs):
            return self._songs[row]
        return None

    def set_playing(self, song_id):
        """高亮正在播放行的序号为红色 ▶"""
        self._playing_id = str(song_id or "")
        for row in range(len(self._songs)):
            self._fill_index(row)

    # ---------- 填充 ----------
    def _fill_row(self, row):
        s = self._songs[row]
        self._fill_index(row)
        self.setItem(row, 1, self._item(s.name, None, bold=True))
        self.setItem(row, 2, self._item(s.artist or "-", _GRAY))
        self.setItem(row, 3, self._item(s.album or "-", _GRAY))
        self.setItem(row, 4, self._item(s.duration_text, _GRAY))

    def _fill_index(self, row):
        s = self._songs[row]
        if self._playing_id and str(s.id) == self._playing_id:
            it = QTableWidgetItem("▶")
            it.setForeground(QColor(_RED))
        else:
            it = QTableWidgetItem(str(row + 1))
            it.setForeground(QColor(_GRAY))
        it.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 0, it)

    @staticmethod
    def _item(text, color=None, bold=False):
        it = QTableWidgetItem(text)
        if color:
            it.setForeground(QColor(color))
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        return it

    def _on_double(self, index):
        s = self.song_at(index.row())
        if s:
            self.play_requested.emit(s, index.row())
