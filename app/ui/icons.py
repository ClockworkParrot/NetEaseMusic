# -*- coding: utf-8 -*-
"""SVG 图标库：全部为内联 SVG，经 QSvgRenderer 渲染为 QIcon/QPixmap，无需外部资源。

用法：
    make_icon("play", "#EC4141", 18)   -> QIcon
    make_pixmap("note", "#FFF", 40)    -> QPixmap
    rounded_pixmap(pm, 8)              -> 圆角图片（封面）
"""
from PyQt5.QtCore import Qt, QByteArray, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QGuiApplication
from PyQt5.QtSvg import QSvgRenderer

# {c} 为颜色占位符；默认描边风格，fill="{c}" stroke="none" 表示实心
_ICONS = {
    "compass": '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2.3 4.7-4.7 2.3 2.3-4.7z" fill="{c}" stroke="none"/>',
    "download": '<path d="M12 3.5v11M7 9.5l5 4.5 5-4.5M4.5 19.5h15"/>',
    "folder": '<path d="M3.5 7a2 2 0 0 1 2-2h4.2l2 2h7.3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13.5a2 2 0 0 1-2-2z"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>',
    "back": '<path d="M14.5 5.5L8 12l6.5 6.5"/>',
    "forward": '<path d="M9.5 5.5L16 12l-6.5 6.5"/>',
    "play": '<path d="M8.5 5.5v13L19 12z" fill="{c}" stroke="none"/>',
    "pause": '<rect x="7" y="5" width="3.4" height="14" rx="1" fill="{c}" stroke="none"/><rect x="13.6" y="5" width="3.4" height="14" rx="1" fill="{c}" stroke="none"/>',
    "prev": '<path d="M6.5 5.5v13"/><path d="M19 6.5v11L9.5 12z" fill="{c}" stroke="none"/>',
    "next": '<path d="M17.5 5.5v13"/><path d="M5 6.5v11L14.5 12z" fill="{c}" stroke="none"/>',
    "heart": '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
    "heart_fill": '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" fill="{c}" stroke="none"/>',
    "volume": '<path d="M11 5.5L7 9H4v6h3l4 3.5z" fill="{c}" stroke="none"/><path d="M15.5 9a4.2 4.2 0 0 1 0 6M18 6.8a7.5 7.5 0 0 1 0 10.4"/>',
    "loop": '<path d="M17 3.5l3 3-3 3"/><path d="M20 6.5H8a4.5 4.5 0 0 0-4.5 4.5"/><path d="M7 20.5l-3-3 3-3"/><path d="M4 17.5h12a4.5 4.5 0 0 0 4.5-4.5"/>',
    "shuffle": '<path d="M16 3.5h4.5V8M4 20L20.5 3.5M20.5 16v4.5H16M15 15l5.5 5.5M4 4l5 5"/>',
    "list": '<path d="M4 6.5h16M4 12h16M4 17.5h9"/><circle cx="17.5" cy="17.5" r="2" fill="{c}" stroke="none"/>',
    "settings": '<path d="M4 7h3M12 7h8M4 17h8M17 17h3"/><circle cx="9.5" cy="7" r="2.2"/><circle cx="14.5" cy="17" r="2.2"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8"/>',
    "moon": '<path d="M20.5 13.5A8.5 8.5 0 1 1 10.5 3.5a7 7 0 0 0 10 10z" fill="{c}" stroke="none"/>',
    "note": '<path d="M9 17.5V6.2l10-2v11.3"/><circle cx="6.8" cy="17.5" r="2.4"/><circle cx="16.8" cy="15.5" r="2.4"/>',
    "close": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V5.5a1.5 1.5 0 0 1 1.5-1.5h2a1.5 1.5 0 0 1 1.5 1.5V7M6.5 7l1 12.5h9l1-12.5M10 11v5.5M14 11v5.5"/>',
    "friend": '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19.5c0-3 2.5-5.5 5.5-5.5s5.5 2.5 5.5 5.5"/><circle cx="16.8" cy="9.5" r="2.6"/><path d="M15.5 14.2c2.8.3 5 2.6 5 5.3"/>',
    "video": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M10.5 9.2l5 2.8-5 2.8z" fill="{c}" stroke="none"/>',
    "cloud": '<path d="M7 18.5h10a4 4 0 0 0 .9-7.9A6 6 0 0 0 6.2 9.4 4.6 4.6 0 0 0 7 18.5z"/>',
    "plus": '<path d="M12 5.5v13M5.5 12h13"/>',
    "radio": '<circle cx="12" cy="12" r="2.2" fill="{c}" stroke="none"/><path d="M7.8 16.2a6 6 0 0 1 0-8.4M16.2 7.8a6 6 0 0 1 0 8.4M5 19a10 10 0 0 1 0-14M19 5a10 10 0 0 1 0 14"/>',
    "refresh": '<path d="M19 12a7 7 0 1 1-2.05-4.95"/><path d="M19 3.5V8h-4.5"/>',
    "lyrics": '<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M8.5 8h7M8.5 11.5h7M8.5 15h4.5"/>',
}

_APP_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect x="2" y="2" width="60" height="60" rx="14" fill="#EC4141"/>'
    '<path d="M27 44V22l18-4v20" fill="none" stroke="#FFFFFF" stroke-width="4" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="23" cy="44" r="5" fill="#FFFFFF"/>'
    '<circle cx="41" cy="38" r="5" fill="#FFFFFF"/>'
    '</svg>'
)


def _svg(name, color):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            'stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>'
            % (color, _ICONS[name].replace("{c}", color)))


def _dpr():
    scr = QGuiApplication.primaryScreen()
    return scr.devicePixelRatio() if scr else 1.0


def _render(svg, size):
    """渲染 SVG 字符串为高分辨率 QPixmap"""
    dpr = _dpr()
    px = max(1, int(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(dpr)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


def make_icon(name, color="#5C5C5C", size=18):
    """图标名 + 颜色 → QIcon"""
    return QIcon(_render(_svg(name, color), size))


def make_pixmap(name, color="#5C5C5C", size=24):
    """图标名 + 颜色 → QPixmap"""
    return _render(_svg(name, color), size)


def app_icon(size=64):
    """应用图标：红色圆角方块 + 白色音符"""
    return QIcon(_render(_APP_ICON_SVG, size))


def rounded_pixmap(src, radius=8):
    """裁剪为圆角方形图片（封面用），无图时返回音符占位"""
    if src is None or src.isNull():
        pm = make_pixmap("note", "#B9B9B9", 96)
        return pm
    side = min(src.width(), src.height())
    square = src.copy((src.width() - side) // 2, (src.height() - side) // 2, side, side)
    dpr = _dpr()
    out = QPixmap(int(side * dpr), int(side * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, side, side, radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, side, side, square)
    p.end()
    return out
