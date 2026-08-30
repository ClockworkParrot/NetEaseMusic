# -*- coding: utf-8 -*-
"""歌单详情页：大封面 + 标题/创建者/数量 + 操作按钮 + 歌曲表"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from app.ui.icons import make_icon, rounded_pixmap
from app.ui.widgets.song_table import SongTable

_WHITE = "#FFFFFF"

KIND_TEXT = {"playlist": "歌单", "album": "专辑", "song": "单曲"}


class PlaylistPage(QWidget):
    play_all_requested = pyqtSignal(list)
    download_all_requested = pyqtSignal(list)
    download_selected_requested = pyqtSignal(list)
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.playlist = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # ---- 顶部信息区 ----
        top = QHBoxLayout()
        top.setSpacing(20)

        self.cover = QLabel()
        self.cover.setFixedSize(150, 150)
        top.addWidget(self.cover)

        info = QVBoxLayout()
        info.setSpacing(8)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(8)
        self.tag = QLabel("歌单")
        self.tag.setObjectName("Tag")
        self.title = QLabel("歌单标题")
        self.title.setObjectName("PlaylistTitle")
        tag_row.addWidget(self.tag)
        tag_row.addWidget(self.title, 1)
        info.addLayout(tag_row)

        self.meta_creator = QLabel("")
        self.meta_creator.setObjectName("PlaylistMeta")
        self.meta_count = QLabel("")
        self.meta_count.setObjectName("PlaylistMeta")
        info.addWidget(self.meta_creator)
        info.addWidget(self.meta_count)
        info.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        play_all = QPushButton("  播放全部")
        play_all.setObjectName("Primary")
        play_all.setIcon(make_icon("play", _WHITE, 13))
        play_all.setCursor(Qt.PointingHandCursor)
        play_all.clicked.connect(self._on_play_all)
        btns.addWidget(play_all)

        dl_all = QPushButton("  下载全部")
        dl_all.setObjectName("Secondary")
        dl_all.setIcon(make_icon("download", "#5C5C5C", 14))
        dl_all.setCursor(Qt.PointingHandCursor)
        dl_all.clicked.connect(lambda: self.download_all_requested.emit(
            self.playlist.songs if self.playlist else []))
        btns.addWidget(dl_all)

        dl_sel = QPushButton("  下载选中")
        dl_sel.setObjectName("Secondary")
        dl_sel.setCursor(Qt.PointingHandCursor)
        dl_sel.clicked.connect(lambda: self.download_selected_requested.emit(
            self.table.selected_songs()))
        btns.addWidget(dl_sel)

        export_btn = QPushButton("  导出歌单")
        export_btn.setObjectName("Secondary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self.export_requested.emit)
        btns.addWidget(export_btn)
        btns.addStretch(1)
        info.addLayout(btns)

        info.addStretch(1)
        top.addLayout(info, 1)
        outer.addLayout(top)

        # ---- 歌曲表 ----
        self.table = SongTable()
        outer.addWidget(self.table, 1)

        self.set_cover(None)

    # ---------- 对外 ----------
    def set_playlist(self, pl):
        self.playlist = pl
        self.tag.setText(KIND_TEXT.get(pl.kind, "歌单"))
        self.title.setText(pl.title or "未知标题")
        self.meta_creator.setText(f"创建者：{pl.creator}" if pl.creator else "")
        self.meta_count.setText(f"共 {len(pl.songs)} 首")
        self.table.set_songs(pl.songs)
        self.set_cover(None)

    def set_cover(self, pixmap):
        pm = rounded_pixmap(pixmap, 10)
        self.cover.setPixmap(pm.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ---------- 内部 ----------
    def _on_play_all(self):
        if self.playlist:
            self.play_all_requested.emit(self.playlist.songs)
