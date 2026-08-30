# -*- coding: utf-8 -*-
"""轻提示 Toast：底部居中浮层，自动消失"""
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QLabel


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(
            "background: rgba(0,0,0,0.75); color: #FFFFFF;"
            "padding: 9px 20px; border-radius: 8px; font-size: 13px;"
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, ms=2200):
        self.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        if p:
            self.move((p.width() - self.width()) // 2, p.height() - 150)
        self.show()
        self.raise_()
        self._timer.start(ms)
