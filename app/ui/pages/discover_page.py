# -*- coding: utf-8 -*-
"""发现页：红色 Banner 链接解析 + 搜索结果列表"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFrame)
from app.ui.icons import make_icon
from app.ui.widgets.song_table import SongTable

_WHITE = "#FFFFFF"


class DiscoverPage(QWidget):
    resolve_requested = pyqtSignal(str)       # Banner 链接解析
    import_requested = pyqtSignal()           # 导入歌单文件
    play_all_requested = pyqtSignal(list)
    download_requested = pyqtSignal(list)     # 选中歌曲

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        # ---- 红色 Banner：链接解析 ----
        banner = QWidget()
        banner.setObjectName("Banner")
        banner.setFixedHeight(108)
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(26, 18, 26, 18)
        bl.setSpacing(18)

        text_box = QVBoxLayout()
        text_box.setSpacing(6)
        t1 = QLabel("音乐，随下随听")
        t1.setObjectName("BannerTitle")
        t2 = QLabel("粘贴歌单 / 专辑 / 单曲链接，一键解析并下载")
        t2.setObjectName("BannerSub")
        text_box.addWidget(t1)
        text_box.addWidget(t2)
        bl.addLayout(text_box)

        self.link_input = QLineEdit()
        self.link_input.setObjectName("LinkInput")
        self.link_input.setPlaceholderText("https://music.163.com/playlist?id=...")
        self.link_input.returnPressed.connect(lambda: self.resolve_requested.emit(self.link_input.text().strip()))
        bl.addWidget(self.link_input, 1)

        resolve_btn = QPushButton("解析")
        resolve_btn.setObjectName("Primary")
        resolve_btn.setCursor(Qt.PointingHandCursor)
        resolve_btn.clicked.connect(lambda: self.resolve_requested.emit(self.link_input.text().strip()))
        bl.addWidget(resolve_btn)
        outer.addWidget(banner)

        # ---- 搜索结果卡片 ----
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 14)
        cl.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel("搜索结果")
        self.title.setObjectName("PageTitle")
        self.count = QLabel("")
        self.count.setObjectName("PageCount")
        head.addWidget(self.title)
        head.addWidget(self.count)
        head.addStretch(1)

        play_all = QPushButton("  播放全部")
        play_all.setObjectName("Secondary")
        play_all.setIcon(make_icon("play", "#5C5C5C", 13))
        play_all.setCursor(Qt.PointingHandCursor)
        play_all.clicked.connect(lambda: self.play_all_requested.emit(self.table.songs()))
        head.addWidget(play_all)

        dl_btn = QPushButton("  下载选中")
        dl_btn.setObjectName("Primary")
        dl_btn.setIcon(make_icon("download", _WHITE, 14))
        dl_btn.setCursor(Qt.PointingHandCursor)
        dl_btn.clicked.connect(lambda: self.download_requested.emit(self.table.selected_songs()))
        head.addWidget(dl_btn)

        imp_btn = QPushButton("  导入歌单")
        imp_btn.setObjectName("Secondary")
        imp_btn.setCursor(Qt.PointingHandCursor)
        imp_btn.clicked.connect(self.import_requested.emit)
        head.addWidget(imp_btn)
        cl.addLayout(head)

        self.table = SongTable()
        cl.addWidget(self.table, 1)
        outer.addWidget(card, 1)

    # ---------- 对外 ----------
    def set_results(self, songs):
        self.table.set_songs(songs)
        self.count.setText(f"共 {len(songs)} 首" if songs else "")
