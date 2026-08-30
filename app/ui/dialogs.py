# -*- coding: utf-8 -*-
"""设置对话框：Cookie / 网络代理"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPlainTextEdit, QLineEdit, QComboBox,
                             QCheckBox, QDialogButtonBox, QFormLayout)


class CookieDialog(QDialog):
    """粘贴网易云完整 Cookie（含 MUSIC_U），留空即清除"""

    def __init__(self, current="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cookie 设置")
        self.setFixedSize(460, 260)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        tip = QLabel("请粘贴从浏览器复制的完整 Cookie 字符串（包含 MUSIC_U 等字段）。\n留空保存则清除 Cookie。")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("MUSIC_U=xxxxxxxx...; os=pc; ...")
        self.edit.setPlainText(current or "")
        lay.addWidget(self.edit, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def get_cookie(self):
        return self.edit.toPlainText().strip()


class ProxyDialog(QDialog):
    """HTTP / SOCKS5 代理设置"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("网络代理设置")
        self.setFixedWidth(380)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        self.enable = QCheckBox("启用代理")
        lay.addWidget(self.enable)

        form = QFormLayout()
        form.setSpacing(8)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["HTTP", "SOCKS5"])
        form.addRow(QLabel("代理类型:"), self.type_combo)
        self.host_edit = QLineEdit("127.0.0.1")
        form.addRow(QLabel("主机:"), self.host_edit)
        self.port_edit = QLineEdit("1080")
        form.addRow(QLabel("端口:"), self.port_edit)
        self.user_edit = QLineEdit()
        form.addRow(QLabel("用户名 (可选):"), self.user_edit)
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        form.addRow(QLabel("密码 (可选):"), self.pass_edit)
        lay.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def get_proxy_dict(self):
        """返回 requests 可用的 proxies 字典；未启用返回 None"""
        if not self.enable.isChecked():
            return None
        host = self.host_edit.text().strip()
        port = self.port_edit.text().strip()
        if not host or not port:
            return None
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text().strip()
        scheme = "socks5" if self.type_combo.currentText() == "SOCKS5" else "http"
        if user and pwd:
            url = f"{scheme}://{user}:{pwd}@{host}:{port}"
        else:
            url = f"{scheme}://{host}:{port}"
        return {"http": url, "https": url}
