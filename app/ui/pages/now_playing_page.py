# -*- coding: utf-8 -*-
"""正在播放页：大封面 + 滚动歌词 + 保存字幕按钮"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QScrollArea, QPushButton, QSizePolicy)
from app.ui.icons import rounded_pixmap

_RED = "#EC4141"
_GRAY = "#8C8C8C"
_LIGHT_LINE = "#5A5A5A"
_DARK_LINE = "#B3B3B3"


class NowPlayingPage(QWidget):
    save_lrc_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._rows = []          # 歌词 QLabel 列表
        self._times = []         # 对应时间 ms
        self._cur = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 18, 30, 18)
        outer.setSpacing(12)

        head = QHBoxLayout()
        head.addStretch(1)
        self.save_btn = QPushButton("  保存歌词到本地")
        self.save_btn.setObjectName("Secondary")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setToolTip("将当前歌词保存为 .lrc 字幕文件")
        self.save_btn.clicked.connect(self.save_lrc_requested.emit)
        head.addWidget(self.save_btn)
        outer.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(36)

        # ---- 左：封面 ----
        left = QVBoxLayout()
        left.addStretch(1)
        self.cover = QLabel()
        self.cover.setFixedSize(230, 230)
        self.cover.setAlignment(Qt.AlignCenter)
        left.addWidget(self.cover)
        left.addStretch(1)
        body.addLayout(left)

        # ---- 右：标题 + 歌词滚动区 ----
        right = QVBoxLayout()
        right.setSpacing(8)
        self.title = QLabel("未在播放")
        self.title.setObjectName("NpTitle")
        self.artist = QLabel("")
        self.artist.setObjectName("NpArtist")
        right.addWidget(self.title)
        right.addWidget(self.artist)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setAttribute(Qt.WA_TranslucentBackground)
        self.host = QWidget()
        self.host.setAttribute(Qt.WA_TranslucentBackground)
        self.lrc_lay = QVBoxLayout(self.host)
        self.lrc_lay.setContentsMargins(0, 10, 0, 10)
        self.lrc_lay.setSpacing(14)
        self.lrc_lay.addStretch(1)
        self.scroll.setWidget(self.host)
        right.addWidget(self.scroll, 1)
        body.addLayout(right, 1)

        outer.addLayout(body, 1)
        self.set_cover(None)

    # ---------- 状态 ----------
    def set_cover(self, pixmap):
        if pixmap is None or isinstance(pixmap, QPixmap) and pixmap.isNull():
            self.cover.setPixmap(rounded_pixmap(None, 12))
        else:
            self.cover.setPixmap(rounded_pixmap(pixmap, 12))

    def set_track(self, title, artist):
        self.title.setText(title or "未在播放")
        self.artist.setText(artist or "")

    def set_no_track(self):
        self.set_track("未在播放", "")
        self.set_lyrics([], [], hint="播放歌曲时在这里显示歌词")

    def set_lyrics(self, timed, plain, hint=""):
        """重建歌词行：timed=[(ms, text)]；无歌词时显示 hint"""
        for w in self._rows:
            self.lrc_lay.removeWidget(w)
            w.deleteLater()
        self._rows, self._times = [], []
        self._cur = -1
        if timed:
            for ms, text in timed:
                lb = QLabel(text or "·")
                lb.setObjectName("LrcLine")
                lb.setWordWrap(True)
                lb.setTextInteractionFlags(Qt.NoTextInteraction)
                self.lrc_lay.insertWidget(self.lrc_lay.count() - 1, lb)
                self._rows.append(lb)
                self._times.append(ms)
        else:
            msg = hint or (("\n".join(plain)) if plain else "暂无歌词")
            lb = QLabel(msg)
            lb.setObjectName("LrcLine")
            lb.setAlignment(Qt.AlignCenter)
            self.lrc_lay.insertWidget(0, lb)
            self._rows.append(lb)
            self._times.append(None)
        self._style(0)

    def set_position(self, ms):
        """播放位置驱动高亮（行未变化时不重绘）"""
        if not self._times or self._times[0] is None:
            return
        idx, lo, hi = -1, 0, len(self._times) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._times[mid] <= ms:
                idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if idx != self._cur:
            self._cur = idx
            self._style(max(idx, 0))
            row = self._rows[max(idx, 0)]
            self.scroll.ensureWidgetVisible(row, 0, int(self.scroll.height() * 0.28))

    # ---------- 内部 ----------
    def _style(self, _active=None):
        has_timeline = bool(self._times) and self._times[0] is not None
        for i, lb in enumerate(self._rows):
            if has_timeline and i == self._cur:
                lb.setStyleSheet(f"color: {_RED}; font-size: 17px; font-weight: 600; background: transparent;")
            else:
                lb.setStyleSheet(f"color: {_GRAY}; font-size: 15px; background: transparent;")
            lb.adjustSize()
