# -*- coding: utf-8 -*-
"""底部播放条：封面/歌曲信息/喜欢 + 播放控制/进度 + 音量/模式/列表"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QSlider, QToolButton, QSizePolicy)
from app.ui.icons import make_icon, rounded_pixmap

_GRAY = "#8C8C8C"
_RED = "#EC4141"


class _Slider(QSlider):
    """带拖拽保护的滑条：拖动中不回写位置，松手发 seek 信号"""
    seek_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._dragging = False

    def is_dragging(self):
        return self._dragging

    def mousePressEvent(self, ev):
        self._dragging = True
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self._dragging = False
        self.seek_requested.emit(self.value())


class _CoverLabel(QLabel):
    """可点击封面：跳转到正在播放页"""
    clicked = pyqtSignal()

    def mousePressEvent(self, ev):
        self.clicked.emit()

    def enterEvent(self, ev):
        self.setCursor(Qt.PointingHandCursor)
        super().enterEvent(ev)


class PlayerBar(QWidget):
    play_toggled = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    seek_requested = pyqtSignal(int)        # ms
    volume_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(str)          # loop / shuffle
    like_toggled = pyqtSignal(bool)
    open_downloads = pyqtSignal()
    cover_clicked = pyqtSignal()

    MODES = [("loop", "列表循环"), ("shuffle", "随机播放")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlayerBar")
        self.setFixedHeight(68)
        self._mode_idx = 0
        self._liked = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 18, 8)
        lay.setSpacing(12)

        # ---- 左：封面 / 信息 / 喜欢 ----
        self.cover = _CoverLabel()
        self.cover.setFixedSize(44, 44)
        self.cover.clicked.connect(self.cover_clicked.emit)
        lay.addWidget(self.cover)

        meta = QVBoxLayout()
        meta.setSpacing(3)
        self.title = QLabel("未在播放")
        self.title.setObjectName("SongTitle")
        self.title.setFixedWidth(170)
        self.artist = QLabel("  ")
        self.artist.setObjectName("SongArtist")
        self.artist.setFixedWidth(170)
        meta.addWidget(self.title)
        meta.addWidget(self.artist)
        lay.addLayout(meta)

        self.like_btn = self._icon_btn("heart", 30)
        self.like_btn.setToolTip("喜欢")
        self.like_btn.clicked.connect(self._toggle_like)
        lay.addWidget(self.like_btn)

        lay.addStretch(1)

        # ---- 中：控制按钮 + 进度 ----
        center = QVBoxLayout()
        center.setSpacing(4)

        ctrl = QHBoxLayout()
        ctrl.addStretch(1)
        self.prev_btn = self._icon_btn("prev", 32, 16)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        self.play_btn = QToolButton()
        self.play_btn.setObjectName("PlayBtn")
        self.play_btn.setIcon(make_icon("play", "#FFFFFF", 18))
        self.play_btn.setFixedSize(34, 34)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self.play_toggled.emit)
        self.next_btn = self._icon_btn("next", 32, 16)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        ctrl.addWidget(self.prev_btn)
        ctrl.addSpacing(10)
        ctrl.addWidget(self.play_btn)
        ctrl.addSpacing(10)
        ctrl.addWidget(self.next_btn)
        ctrl.addStretch(1)
        center.addLayout(ctrl)

        prog = QHBoxLayout()
        prog.setSpacing(8)
        self.time_cur = QLabel("00:00")
        self.time_cur.setObjectName("TimeLabel")
        self.time_total = QLabel("00:00")
        self.time_total.setObjectName("TimeLabel")
        self.slider = _Slider()
        self.slider.setRange(0, 0)
        self.slider.setFixedWidth(360)
        self.slider.seek_requested.connect(self.seek_requested.emit)
        prog.addStretch(1)
        prog.addWidget(self.time_cur)
        prog.addWidget(self.slider)
        prog.addWidget(self.time_total)
        prog.addStretch(1)
        center.addLayout(prog)

        cw = QWidget()
        cw.setLayout(center)
        lay.addWidget(cw, 1)

        lay.addStretch(1)

        # ---- 右：模式 / 音量 / 列表 ----
        self.mode_btn = self._icon_btn("loop", 30)
        self.mode_btn.clicked.connect(self._cycle_mode)
        lay.addWidget(self.mode_btn)

        self.volume_btn = self._icon_btn("volume", 30)
        lay.addWidget(self.volume_btn)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(84)
        self.volume.valueChanged.connect(self.volume_changed.emit)
        lay.addWidget(self.volume)

        list_btn = self._icon_btn("list", 30)
        list_btn.setToolTip("下载管理")
        list_btn.clicked.connect(self.open_downloads.emit)
        lay.addWidget(list_btn)

        # 默认封面占位
        self.set_cover(None)

    # ---------- 构建 ----------
    def _icon_btn(self, icon, box, size=17):
        b = QToolButton()
        b.setObjectName("IconButton")
        b.setIcon(make_icon(icon, _GRAY, size))
        b.setFixedSize(box, box)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _toggle_like(self):
        self._liked = not self._liked
        self.set_liked(self._liked)
        self.like_toggled.emit(self._liked)

    def _cycle_mode(self):
        self._mode_idx = (self._mode_idx + 1) % len(self.MODES)
        mode, text = self.MODES[self._mode_idx]
        self.mode_btn.setIcon(make_icon(mode, _RED, 17))
        self.mode_changed.emit(mode)
        self.setToolTip(text)

    # ---------- 状态 ----------
    def set_song(self, song):
        self.title.setText(song.name if song else "未在播放")
        self.artist.setText(song.artist if song and song.artist else "  ")
        self.set_position(0, song.duration_ms if song else 0)

    def set_cover(self, pixmap):
        self.cover.setPixmap(rounded_pixmap(pixmap, 8))

    def set_playing(self, playing):
        self.play_btn.setIcon(make_icon("pause" if playing else "play", "#FFFFFF", 18))

    def set_position(self, ms, duration):
        self.time_cur.setText(self._fmt(ms))
        self.time_total.setText(self._fmt(duration) if duration > 0 else "00:00")
        if not self.slider.is_dragging():
            self.slider.blockSignals(True)
            self.slider.setRange(0, max(int(duration), 0))
            self.slider.setValue(int(ms))
            self.slider.blockSignals(False)

    def set_liked(self, liked):
        self._liked = liked
        self.like_btn.setIcon(make_icon("heart_fill" if liked else "heart",
                                        _RED if liked else _GRAY, 17))

    def set_volume(self, v):
        self.volume.blockSignals(True)
        self.volume.setValue(int(v))
        self.volume.blockSignals(False)

    @staticmethod
    def _fmt(ms):
        if ms <= 0:
            return "00:00"
        s = int(ms // 1000)
        return f"{s // 60:02d}:{s % 60:02d}"
