# -*- coding: utf-8 -*-
"""主题：仿网易云官方 2022+ PC 客户端视觉（主红 #EC4141）。

LIGHT / DARK 为颜色字典，build_qss(c) 生成整站 QSS。
STATE_COLOR 供下载页状态文本着色。
"""

ACCENT = "#EC4141"

LIGHT = {
    "accent": ACCENT,
    "accent_hover": "#D33939",
    "accent_disabled": "#F5BFBF",
    "accent_soft": "#FDF0F0",
    "bg": "#FFFFFF",
    "bg_page": "#FAFAFB",
    "bg_side": "#FAFAFB",
    "bg_input": "#F2F3F5",
    "border": "#EAEAEA",
    "border_mid": "#D8D8DC",
    "text": "#333333",
    "text_sub": "#8C8C8C",
    "hover": "#F1F1F3",
    "sel_row": "#FDF0F0",
    "bar": "#FFFFFF",
    "scroll": "#D9D9D9",
}

DARK = {
    "accent": ACCENT,
    "accent_hover": "#F05555",
    "accent_disabled": "#6A3A3A",
    "accent_soft": "#3A2A2A",
    "bg": "#1E1E20",
    "bg_page": "#17171A",
    "bg_side": "#1B1B1E",
    "bg_input": "#2A2A2E",
    "border": "#333338",
    "border_mid": "#3C3C42",
    "text": "#E6E6E8",
    "text_sub": "#8F8F95",
    "hover": "#2C2C30",
    "sel_row": "#3A2A2A",
    "bar": "#242427",
    "scroll": "#3A3A3E",
}

# 下载任务状态 → 状态文本颜色（两套主题通用）
STATE_COLOR = {
    "wait": "#8C8C8C",
    "run": "#F59E0B",
    "done": "#2E9E5B",
    "fail": "#EC4141",
    "exists": "#8C8C8C",
}

STATE_TEXT = {
    "wait": "等待中",
    "run": "下载中",
    "done": "已完成",
    "fail": "失败",
    "exists": "已存在",
}

FONT_STACK = '"Microsoft YaHei UI","Microsoft YaHei","PingFang SC","Noto Sans CJK SC","Segoe UI",sans-serif'


def build_qss(c):
    """根据颜色字典生成全套 QSS"""
    return f"""
* {{ font-family: {FONT_STACK}; outline: none; }}
QMainWindow {{ background: {c['bg']}; }}
QWidget#Root {{ background: {c['bg']}; }}

/* ---------- 顶栏 ---------- */
#TitleBar {{ background: {c['bg']}; border-bottom: 1px solid {c['border']}; }}
#LogoText {{ color: {c['text']}; font-size: 15px; font-weight: bold; background: transparent; }}
#LogoBadge {{ color: {c['text_sub']}; font-size: 10px; background: transparent; }}
#SearchBox {{
    background: {c['bg_input']}; border: 1px solid transparent; border-radius: 16px;
    padding: 5px 12px 5px 12px; font-size: 13px; color: {c['text']};
    selection-background-color: {c['accent']};
}}
#SearchBox:focus {{ background: {c['bg']}; border: 1px solid {c['accent']}; }}

/* ---------- 侧边栏 ---------- */
#Sidebar {{ background: {c['bg_side']}; border-right: 1px solid {c['border']}; }}
#SectionLabel {{ color: {c['text_sub']}; font-size: 12px; padding: 10px 18px 4px; background: transparent; }}
#NavItem {{
    background: transparent; border: none; border-radius: 6px;
    padding: 8px 12px; margin: 1px 12px; text-align: left;
    color: {c['text']}; font-size: 13px; spacing: 8px;
}}
#NavItem:hover {{ background: {c['hover']}; }}
#NavItem:checked {{ background: {c['accent_soft']}; color: {c['accent']}; font-weight: 600; }}
#SideItem {{
    color: {c['text_sub']}; font-size: 12px; padding: 5px 30px;
    background: transparent; border-radius: 6px; margin: 0 12px;
}}
#SideItem:hover {{ color: {c['accent']}; background: {c['hover']}; }}

/* ---------- 页面 ---------- */
#Page {{ background: {c['bg_page']}; }}
#Card {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 10px; }}
#Banner {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #F25858, stop:1 #C62828);
    border-radius: 12px; border: none;
}}
#BannerTitle {{ color: #FFFFFF; font-size: 18px; font-weight: bold; background: transparent; }}
#BannerSub {{ color: rgba(255, 255, 255, 0.85); font-size: 12px; background: transparent; }}
#LinkInput {{
    background: rgba(255, 255, 255, 0.92); border: none; border-radius: 16px;
    padding: 7px 14px; font-size: 13px; color: #333333;
}}
#PageTitle {{ color: {c['text']}; font-size: 16px; font-weight: bold; background: transparent; }}
#PageCount {{ color: {c['text_sub']}; font-size: 12px; background: transparent; }}
#Tag {{
    color: {c['accent']}; border: 1px solid {c['accent']}; border-radius: 4px;
    padding: 1px 6px; font-size: 12px; background: transparent;
}}
#PlaylistTitle {{ color: {c['text']}; font-size: 20px; font-weight: bold; background: transparent; }}
#PlaylistMeta {{ color: {c['text_sub']}; font-size: 12px; background: transparent; }}

/* ---------- 按钮 ---------- */
QPushButton#Primary {{
    background: {c['accent']}; color: #FFFFFF; border: none; border-radius: 15px;
    padding: 7px 20px; font-size: 13px; font-weight: 500; spacing: 6px;
}}
QPushButton#Primary:hover {{ background: {c['accent_hover']}; }}
QPushButton#Primary:disabled {{ background: {c['accent_disabled']}; }}
QPushButton#Secondary {{
    background: transparent; color: {c['text']}; border: 1px solid {c['border_mid']};
    border-radius: 15px; padding: 6px 18px; font-size: 13px; spacing: 6px;
}}
QPushButton#Secondary:hover {{ color: {c['accent']}; border-color: {c['accent']}; background: {c['accent_soft']}; }}
QToolButton#IconButton {{ background: transparent; border: none; border-radius: 14px; padding: 5px; }}
QToolButton#IconButton:hover {{ background: {c['hover']}; }}

/* ---------- 表格 ---------- */
QTableWidget {{
    background: transparent; border: none; font-size: 13px; color: {c['text']};
    gridline-color: transparent; alternate-background-color: transparent;
    selection-background-color: {c['sel_row']}; selection-color: {c['text']};
}}
QTableWidget::item {{ padding: 2px 6px; border: none; }}
QTableWidget::item:hover {{ background: {c['hover']}; }}
QTableWidget::item:selected {{ background: {c['sel_row']}; }}
QHeaderView::section {{
    background: transparent; color: {c['text_sub']}; font-size: 12px; font-weight: normal;
    border: none; border-bottom: 1px solid {c['border']}; padding: 7px 6px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ---------- 输入控件 ---------- */
QLineEdit {{
    background: {c['bg_input']}; border: 1px solid transparent; border-radius: 6px;
    padding: 6px 10px; font-size: 13px; color: {c['text']};
    selection-background-color: {c['accent']};
}}
QLineEdit:focus {{ background: {c['bg']}; border: 1px solid {c['accent']}; }}
QComboBox {{
    background: {c['bg_input']}; border: 1px solid transparent; border-radius: 6px;
    padding: 5px 10px; color: {c['text']}; font-size: 13px;
}}
QComboBox:hover {{ background: {c['hover']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {c['bg']}; color: {c['text']}; border: 1px solid {c['border']};
    selection-background-color: {c['accent_soft']}; selection-color: {c['accent']};
}}
QSpinBox {{
    background: {c['bg_input']}; border: 1px solid transparent; border-radius: 6px;
    padding: 4px 8px; color: {c['text']}; font-size: 13px;
}}
QPlainTextEdit {{
    background: {c['bg_input']}; border: 1px solid {c['border_mid']}; border-radius: 6px;
    padding: 8px; color: {c['text']}; font-size: 12px;
}}

/* ---------- 滑条（进度 / 音量） ---------- */
QSlider {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border_mid']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 10px; height: 10px; margin: -3px 0; background: {c['accent']}; border-radius: 5px;
}}
QSlider::handle:horizontal:hover {{ width: 12px; height: 12px; margin: -4px 0; }}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background: {c['bg_input']}; border: none; border-radius: 3px;
    max-height: 6px; font-size: 1px; color: transparent;
}}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}

/* ---------- 播放条 ---------- */
#PlayerBar {{ background: {c['bar']}; border-top: 1px solid {c['border']}; }}
#SongTitle {{ color: {c['text']}; font-size: 13px; font-weight: 600; background: transparent; }}
#SongArtist {{ color: {c['text_sub']}; font-size: 11px; background: transparent; }}
#TimeLabel {{ color: {c['text_sub']}; font-size: 11px; background: transparent; }}
#PlayBtn {{ background: {c['accent']}; border: none; border-radius: 17px; padding: 8px; }}
#PlayBtn:hover {{ background: {c['accent_hover']}; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 2px 2px 0; }}
QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c['text_sub']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0 2px 2px 2px; }}
QScrollBar::handle:horizontal {{ background: {c['scroll']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['text_sub']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ---------- 菜单 / 提示 / 对话框 ---------- */
QMenu {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 24px; border-radius: 5px; color: {c['text']}; font-size: 13px; }}
QMenu::item:selected {{ background: {c['accent_soft']}; color: {c['accent']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 8px; }}
QToolTip {{
    background: {c['bg']}; color: {c['text']}; border: 1px solid {c['border_mid']};
    padding: 4px 8px; font-size: 12px;
}}
QMessageBox {{ background: {c['bg']}; }}
QMessageBox QLabel {{ color: {c['text']}; font-size: 13px; }}
QMessageBox QPushButton {{
    background: {c['bg_input']}; color: {c['text']}; border: 1px solid {c['border_mid']};
    border-radius: 6px; padding: 5px 16px; font-size: 13px; min-width: 60px;
}}
QMessageBox QPushButton:hover {{ color: {c['accent']}; border-color: {c['accent']}; }}
QFileDialog {{ background: {c['bg']}; }}

/* ---------- 新UI组件 ---------- */
#AppTitle {{ color: {c['text']}; font-size: 16px; font-weight: bold; background: transparent; }}
#SearchInput {{ background: {c['bg_input']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 17px; padding: 4px 14px; font-size: 13px; }}
#SearchInput:focus {{ border-color: {c['accent']}; }}
QLineEdit#SearchInput QToolButton {{ background: transparent; }}
#ThemeButton {{ background: transparent; border: none; border-radius: 14px; padding: 5px; }}
#ThemeButton:hover {{ background: {c['hover']}; }}
#SimplifiedSidebar {{ background: {c['bg_side']}; border-right: 1px solid {c['border']}; }}
#SimplifiedNavItem {{
    color: {c['text_sub']}; font-size: 13px; padding: 8px 12px; border-radius: 8px;
    background: transparent; border: none; text-align: left;
}}
#SimplifiedNavItem:hover {{ background: {c['hover']}; color: {c['text']}; }}
#SimplifiedNavItem:checked {{ background: {c['accent_soft']}; color: {c['accent']}; font-weight: 600; }}
#SimplifiedPlayerBar {{ background: {c['bar']}; border-top: 1px solid {c['border']}; }}
#SimplifiedSongTitle {{ color: {c['text']}; font-size: 13px; font-weight: 600; background: transparent; }}
#SimplifiedSongArtist {{ color: {c['text_sub']}; font-size: 11px; background: transparent; }}
#LyricScroll {{ background: {c['bg']}; border: none; }}
#LyricHost {{ background: {c['bg']}; }}
QSlider {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 12px; height: 12px; margin: -5px 0; background: {c['accent']}; border-radius: 6px; border: none; }}

/* ---------- 对话框 ---------- */
#DialogTitle {{ color: {c['text']}; font-size: 14px; font-weight: bold; background: transparent; }}
#FieldLabel {{ color: {c['text_sub']}; font-size: 12px; background: transparent; }}
"""
