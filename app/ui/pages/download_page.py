# -*- coding: utf-8 -*-
"""下载管理页：参数设置 + 任务列表（实时进度）"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QSpinBox, QCheckBox, QLineEdit, QPushButton,
                             QProgressBar, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QFrame)
from app.core import api
from app.ui.theme import STATE_COLOR, STATE_TEXT
from app.ui.icons import make_icon

_WHITE = "#FFFFFF"
_GRAY = "#8C8C8C"

COLUMNS = ["#", "歌曲", "歌手", "状态", "进度", "信息"]


class DownloadPage(QWidget):
    retry_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    cookie_requested = pyqtSignal()
    proxy_requested = pyqtSignal()
    dir_changed = pyqtSignal(str)
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._bars = {}        # song_id -> QProgressBar
        self._rows = {}        # song_id -> 行号

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        # ---- 设置卡片 ----
        card = QFrame()
        card.setObjectName("Card")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(8)

        def field(text):
            lb = QLabel(text)
            lb.setObjectName("FieldLabel")
            return lb

        cl.addWidget(field("音质"))
        self.quality = QComboBox()
        for br, text in api.QUALITY_LIST:
            self.quality.addItem(text, br)
        self.quality.currentIndexChanged.connect(lambda _: self.settings_changed.emit())
        cl.addWidget(self.quality)

        cl.addSpacing(10)
        cl.addWidget(field("并发"))
        self.workers = QSpinBox()
        self.workers.setRange(1, 8)
        self.workers.setValue(3)
        self.workers.valueChanged.connect(lambda _: self.settings_changed.emit())
        cl.addWidget(self.workers)

        cl.addSpacing(10)
        cl.addWidget(field("重试"))
        self.retries = QSpinBox()
        self.retries.setRange(1, 10)
        self.retries.setValue(3)
        self.retries.setToolTip("单个文件下载失败后的重试次数")
        self.retries.valueChanged.connect(lambda _: self.settings_changed.emit())
        cl.addWidget(self.retries)

        cl.addSpacing(10)
        self.embed = QCheckBox("嵌入封面")
        self.embed.setChecked(True)
        self.embed.stateChanged.connect(lambda _: self.settings_changed.emit())
        cl.addWidget(self.embed)

        cl.addSpacing(10)
        cl.addWidget(field("保存目录"))
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        cl.addWidget(self.dir_edit, 1)
        browse = QPushButton("更改")
        browse.setObjectName("Secondary")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse_dir)
        cl.addWidget(browse)

        cookie_btn = QPushButton("Cookie")
        cookie_btn.setObjectName("Secondary")
        cookie_btn.setCursor(Qt.PointingHandCursor)
        cookie_btn.clicked.connect(self.cookie_requested.emit)
        cl.addWidget(cookie_btn)

        proxy_btn = QPushButton("代理")
        proxy_btn.setObjectName("Secondary")
        proxy_btn.setCursor(Qt.PointingHandCursor)
        proxy_btn.clicked.connect(self.proxy_requested.emit)
        cl.addWidget(proxy_btn)
        outer.addWidget(card)

        # ---- 操作行 ----
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.retry_btn = QPushButton("  重试失败")
        self.retry_btn.setObjectName("Primary")
        self.retry_btn.setIcon(make_icon("note", _WHITE, 13))
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self.retry_requested.emit)
        actions.addWidget(self.retry_btn)

        self.cancel_btn = QPushButton("  取消下载")
        self.cancel_btn.setObjectName("Secondary")
        self.cancel_btn.setIcon(make_icon("close", "#5C5C5C", 13))
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        actions.addWidget(self.cancel_btn)

        actions.addStretch(1)
        self.status = QLabel("就绪")
        self.status.setObjectName("PageCount")
        actions.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(260)
        actions.addWidget(self.progress)
        outer.addLayout(actions)

        # ---- 任务列表卡片 ----
        tcard = QFrame()
        tcard.setObjectName("Card")
        tl = QVBoxLayout(tcard)
        tl.setContentsMargins(18, 14, 18, 14)
        tl.setSpacing(8)

        head = QHBoxLayout()
        t1 = QLabel("下载列表")
        t1.setObjectName("PageTitle")
        self.count = QLabel("")
        self.count.setObjectName("PageCount")
        head.addWidget(t1)
        head.addWidget(self.count)
        head.addStretch(1)
        tl.addLayout(head)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMouseTracking(True)
        self.table.setFocusPolicy(Qt.NoFocus)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Fixed)
        self.table.setColumnWidth(0, 52)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 160)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setStretchLastSection(False)
        tl.addWidget(self.table, 1)
        outer.addWidget(tcard, 1)

    # ---------- 参数 ----------
    def get_quality(self):
        return int(self.quality.currentData() or 192000)

    def set_quality(self, br):
        i = self.quality.findData(int(br))
        if i >= 0:
            self.quality.setCurrentIndex(i)

    def get_workers(self):
        return int(self.workers.value())

    def set_workers(self, n):
        self.workers.setValue(int(n))

    def get_retries(self):
        return int(self.retries.value())

    def set_retries(self, n):
        self.retries.setValue(int(n))

    def get_embed(self):
        return self.embed.isChecked()

    def set_embed(self, on):
        self.embed.setChecked(bool(on))

    def set_dir(self, d):
        self.dir_edit.setText(str(d))
        self.dir_edit.setToolTip(str(d))

    def _browse_dir(self):
        from PyQt5.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.dir_edit.text())
        if d:
            self.set_dir(d)
            self.dir_changed.emit(d)

    # ---------- 任务渲染 ----------
    def set_tasks(self, songs):
        """重建任务列表"""
        self._bars.clear()
        self._rows.clear()
        self.table.setRowCount(len(songs))
        for row, s in enumerate(songs):
            self._rows[str(s.id)] = row
            it = QTableWidgetItem(str(row + 1))
            it.setTextAlignment(Qt.AlignCenter)
            it.setForeground(QColor(_GRAY))
            self.table.setItem(row, 0, it)
            name = QTableWidgetItem(s.name)
            f = name.font()
            f.setBold(True)
            name.setFont(f)
            self.table.setItem(row, 1, name)
            artist = QTableWidgetItem(s.artist)
            artist.setForeground(QColor(_GRAY))
            self.table.setItem(row, 2, artist)
            st = QTableWidgetItem(STATE_TEXT["wait"])
            st.setTextAlignment(Qt.AlignCenter)
            st.setForeground(QColor(STATE_COLOR["wait"]))
            self.table.setItem(row, 3, st)
            self.table.setItem(row, 4, QTableWidgetItem("—"))
            self.table.setItem(row, 5, QTableWidgetItem(""))
        self.count.setText(f"共 {len(songs)} 首")
        self.progress.setValue(0)

    def update_task(self, song_id, state, pct, msg):
        """下载线程信号 → 单行刷新"""
        row = self._rows.get(str(song_id))
        if row is None:
            return
        st = self.table.item(row, 3)
        st.setText(STATE_TEXT.get(state, state))
        st.setForeground(QColor(STATE_COLOR.get(state, _GRAY)))

        # 进度列：运行中用进度条控件，其余还原为文本
        if state == "run":
            bar = self._bars.get(str(song_id))
            if bar is None:
                bar = QProgressBar()
                bar.setRange(0, 100)
                self._bars[str(song_id)] = bar
                self.table.setCellWidget(row, 4, bar)
            bar.setValue(int(pct))
        else:
            bar = self._bars.pop(str(song_id), None)
            if bar is not None:
                self.table.removeCellWidget(row, 4)
            pct_text = "100%" if state in ("done", "exists") else "—"
            self.table.setItem(row, 4, QTableWidgetItem(pct_text))

        self.table.setItem(row, 5, QTableWidgetItem(msg))
        self._refresh_overall()

    def _finished_count(self):
        n = 0
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 3)
            if it and it.text() in ("已完成", "已存在", "失败"):
                n += 1
        return n

    def _refresh_overall(self):
        total = max(self.table.rowCount(), 1)
        self.progress.setValue(self._finished_count() * 100 // total)

    def set_status(self, text):
        self.status.setText(text)

    def set_busy(self, busy):
        self.cancel_btn.setEnabled(busy)
        self.retry_btn.setEnabled(not busy)
