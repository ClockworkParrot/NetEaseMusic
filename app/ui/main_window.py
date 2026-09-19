# -*- coding: utf-8 -*-
"""主窗口：顶栏 + 侧边栏 + 三个页面 + 底部播放条 的组装与业务编排"""
import random
import threading
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QDesktopServices
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QFileDialog, QMessageBox, QDialog,
                             QApplication, QLabel, QPushButton, QToolButton, QSizePolicy, QSlider)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

from app.core import api
from app.core import lyrics as lrc_io
from app.core import local_library
from app.core.models import Playlist, Song
from app.core.downloader import DownloadManager, safe_filename
from app.core.playlist_io import export_songs, import_songs
from app.ui.theme import build_qss, LIGHT, DARK
from app.ui.widgets.toast import Toast
from app.ui.dialogs import CookieDialog, ProxyDialog
from app.ui.pages.discover_page import DiscoverPage
from app.ui.pages.playlist_page import PlaylistPage
from app.ui.pages.download_page import DownloadPage
from app.ui.pages.local_page import LocalPage
from app.ui.pages.now_playing_page import NowPlayingPage


class _SimpleSlider(QSlider):
    """简化的进度条滑块"""
    seek_requested = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._dragging = False
    
    def mousePressEvent(self, ev):
        self._dragging = True
        super().mousePressEvent(ev)
    
    def mouseReleaseEvent(self, ev):
        if self._dragging:
            self.seek_requested.emit(self.value())
            self._dragging = False
        super().mouseReleaseEvent(ev)

    def is_dragging(self):
        return self._dragging


class _ClickableLabel(QLabel):
    """可点击的标签（用于跳转到正在播放页）"""
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(ev)


def _fmt_ms(ms):
    """毫秒 → mm:ss"""
    if ms is None or ms <= 0:
        return "00:00"
    s = int(ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


class _Async(QObject):
    """线程池任务的完成/失败信号（跨线程安全投递到主线程）"""
    done = pyqtSignal(object)
    fail = pyqtSignal(str)


class MainWindow(QMainWindow):
    PAGE_DISCOVER, PAGE_PLAYLIST, PAGE_DOWNLOAD, PAGE_LOCAL, PAGE_NOWPLAYING = 0, 1, 2, 3, 4

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.manager = DownloadManager(self)
        self.player = QMediaPlayer(self)

        # 运行状态
        self.playlist = None            # 当前歌单/专辑/单曲集合
        self.play_songs = []            # 播放上下文
        self.play_index = -1
        self.mode = "loop"
        self._pl_entries = []           # 侧栏歌单条目 (kind, id, title)
        self._dark = bool(settings.get("dark"))
        self._now = None                # 正在播放上下文：kind/path/song/title/artist
        self._lrc_plain_text = ""       # 当前歌词原文（保存字幕用）
        self._lrc_saved_path = ""       # 已自动保存的字幕路径
        self._loading_lyrics = False    # 歌词加载中标志（防重复请求）

        self.setWindowTitle("网易云音乐 · 第三方客户端")
        self.setWindowIcon(_app_icon())
        self.resize(1160, 760)
        self.setMinimumSize(960, 640)

        self._build_ui()
        self._connect()

        # 应用保存的偏好
        vol = int(self.settings.get("volume", 70))
        self.player.setVolume(vol)
        if hasattr(self, "vol_slider"):
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(vol)
            self.vol_slider.blockSignals(False)
        self.download_page.set_dir(self.settings.get("save_dir"))
        self.download_page.set_quality(int(self.settings.get("quality", 192000)))
        self.download_page.set_workers(int(self.settings.get("workers", 3)))
        self.download_page.set_retries(int(self.settings.get("retries", 3)))
        self.download_page.set_embed(bool(self.settings.get("embed_cover", True)))
        self.now_page.set_no_track()
        # 启动即扫描本地曲库（默认下载目录，可在本地音乐页更换）
        self._rescan_local()

    # ================= UI 构建 =================
    
    def _create_simplified_sidebar(self):
        """创建简化的侧边栏组件"""
        sidebar = QWidget()
        sidebar.setObjectName("SimplifiedSidebar")
        sidebar.setFixedWidth(200)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(8)
        
        # 导航按钮组
        from app.ui.icons import make_icon
        
        nav_items = [
            ("discover", "发现音乐", "compass"),
            ("local", "本地音乐", "folder"),
            ("downloads", "下载管理", "download"),
        ]
        
        self.nav_buttons = {}
        for key, text, icon_name in nav_items:
            btn = QPushButton(f"  {text}")
            btn.setObjectName("SimplifiedNavItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(make_icon(icon_name, "#8C8C8C", 16))
            btn.clicked.connect(lambda checked, k=key: self._on_nav(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn
        
        layout.addStretch(1)
        
        # 底部设置按钮
        settings_btn = QPushButton("  设置")
        settings_btn.setObjectName("SimplifiedNavItem")
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setIcon(make_icon("settings", "#8C8C8C", 16))
        settings_btn.clicked.connect(self._show_settings_menu)
        layout.addWidget(settings_btn)
        
        return sidebar

    def _show_settings_menu(self):
        """设置弹出菜单：Cookie / 代理 / 下载目录"""
        from PyQt5.QtWidgets import QMenu
        from app.ui.icons import make_icon
        btn = self.sender()
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:%s;color:%s;border:1px solid %s;}"
                           % ("#242427" if self._dark else "#FFF",
                              "#E6E6E8" if self._dark else "#333",
                              "#333338" if self._dark else "#EAEAEA"))
        a_cookie = menu.addAction("设置 Cookie（VIP 试听）")
        a_proxy = menu.addAction("设置代理")
        a_dir = menu.addAction("打开下载目录")
        act = menu.exec_(btn.mapToGlobal(btn.rect().topLeft()))
        if act == a_cookie:
            self._open_cookie()
        elif act == a_proxy:
            self._open_proxy()
        elif act == a_dir:
            self._open_local_dir()
    
    def _create_simplified_player_bar(self):
        """创建简化的播放条组件"""
        player_bar = QWidget()
        player_bar.setObjectName("SimplifiedPlayerBar")
        player_bar.setFixedHeight(60)
        
        layout = QHBoxLayout(player_bar)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(15)
        
        # 播放控制按钮
        controls = QHBoxLayout()
        controls.setSpacing(8)
        
        from app.ui.icons import make_icon
        
        prev_btn = QToolButton()
        prev_btn.setIcon(make_icon("prev", "#8C8C8C", 18))
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.clicked.connect(self._prev)
        controls.addWidget(prev_btn)
        
        self.play_btn = QToolButton()
        self.play_btn.setIcon(make_icon("play", "#EC4141", 20))
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self.play_btn)
        
        next_btn = QToolButton()
        next_btn.setIcon(make_icon("next", "#8C8C8C", 18))
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.clicked.connect(self._next)
        controls.addWidget(next_btn)
        
        layout.addLayout(controls)
        
        # 歌曲信息（点击歌曲标题可进入正在播放页）
        info = QVBoxLayout()
        info.setSpacing(2)
        self.song_title = _ClickableLabel("未播放")
        self.song_title.setObjectName("SimplifiedSongTitle")
        self.song_title.setCursor(Qt.PointingHandCursor)
        self.song_title.clicked.connect(lambda: self._switch_page(self.PAGE_NOWPLAYING))
        self.song_artist = QLabel("")
        self.song_artist.setObjectName("SimplifiedSongArtist")
        info.addWidget(self.song_title)
        info.addWidget(self.song_artist)
        layout.addLayout(info, 1)

        # 歌词按钮（进入正在播放页）
        lrc_btn = QToolButton()
        lrc_btn.setObjectName("ThemeButton")
        lrc_btn.setIcon(make_icon("lyrics", "#8C8C8C", 18))
        lrc_btn.setCursor(Qt.PointingHandCursor)
        lrc_btn.setToolTip("正在播放 / 歌词")
        lrc_btn.clicked.connect(lambda: self._switch_page(self.PAGE_NOWPLAYING))
        layout.addWidget(lrc_btn)
        
        # 时间 + 进度条
        self.time_cur = QLabel("00:00")
        self.time_cur.setObjectName("SimplifiedSongArtist")
        self.time_tot = QLabel("00:00")
        self.time_tot.setObjectName("SimplifiedSongArtist")
        self.progress_slider = _SimpleSlider()
        self.progress_slider.setMinimumWidth(160)
        self.progress_slider.setFixedHeight(20)
        self.progress_slider.seek_requested.connect(self.player.setPosition)
        layout.addWidget(self.time_cur)
        layout.addWidget(self.progress_slider, 1)
        layout.addWidget(self.time_tot)

        # 音量
        vol_icon = QToolButton()
        vol_icon.setObjectName("ThemeButton")
        vol_icon.setIcon(make_icon("volume", "#8C8C8C", 16))
        vol_icon.setCursor(Qt.PointingHandCursor)
        layout.addWidget(vol_icon)
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.valueChanged.connect(self.player.setVolume)
        layout.addWidget(self.vol_slider)

        return player_bar
    
    def _get_theme_icon(self):
        """根据当前主题获取对应的图标"""
        from app.ui.icons import make_icon
        icon_name = "sun" if self._dark else "moon"
        color = "#E6E6E8" if self._dark else "#333333"
        return make_icon(icon_name, color, 16)
    
    def _toggle_theme(self):
        """切换深色/浅色主题"""
        self._dark = not self._dark
        self.settings.set("dark", self._dark)
        QApplication.instance().setStyleSheet(build_qss(DARK if self._dark else LIGHT))
        # 更新主题按钮图标
        if hasattr(self, "theme_btn"):
            self.theme_btn.setIcon(self._get_theme_icon())

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 新顶部栏：应用标题 + 搜索框占位符 + 主题切换
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(15, 10, 15, 10)
        top_bar.setSpacing(15)
        
        # 应用标题
        title_label = QLabel("网易云音乐")
        title_label.setObjectName("AppTitle")
        title_label.setStyleSheet("color: #EC4141; font-size: 16px; font-weight: bold;")
        top_bar.addWidget(title_label)
        
        # 搜索框
        from PyQt5.QtWidgets import QLineEdit
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("搜索音乐 / 歌单 / 歌手…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumHeight(34)
        self.search_input.returnPressed.connect(
            lambda: self.on_query(self.search_input.text().strip()))
        top_bar.addWidget(self.search_input, 1)
        
        # 主题切换按钮
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("ThemeButton")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.theme_btn.setIcon(self._get_theme_icon())
        top_bar.addWidget(self.theme_btn)
        
        outer.addLayout(top_bar)

        # 主体布局：左侧边栏 + 主内容区
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # 使用简化的侧边栏
        self.sidebar = self._create_simplified_sidebar()
        body.addWidget(self.sidebar)

        # 主内容区域
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainContent")
        
        # 创建页面
        self.discover = DiscoverPage()
        self.playlist_page = PlaylistPage()
        self.download_page = DownloadPage()
        self.local_page = LocalPage()
        self.now_page = NowPlayingPage()
        
        # 添加页面到堆栈（顺序必须匹配 PAGE_* 常量）
        self.stack.addWidget(self.discover)        # 0 PAGE_DISCOVER
        self.stack.addWidget(self.playlist_page)   # 1 PAGE_PLAYLIST
        self.stack.addWidget(self.download_page)   # 2 PAGE_DOWNLOAD
        self.stack.addWidget(self.local_page)      # 3 PAGE_LOCAL
        self.stack.addWidget(self.now_page)
        
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        # 使用简化的播放条
        self.player_bar = self._create_simplified_player_bar()
        outer.addWidget(self.player_bar)

        self.toast_tip = Toast(root)

    def _connect(self):
        # 本地音乐页
        self.local_page.play_requested.connect(self._play_local_tracks)
        self.local_page.play_all_requested.connect(self._play_local_tracks)
        self.local_page.lrc_requested.connect(self._fetch_lrc_for_track)
        self.local_page.dir_changed.connect(self._on_local_dir_changed)
        self.local_page.refresh_requested.connect(lambda: self._rescan_local())

        # 正在播放页
        self.now_page.save_lrc_requested.connect(self._save_current_lrc)

        # 发现页
        self.discover.resolve_requested.connect(self.on_query)
        self.discover.import_requested.connect(self._import_playlist)
        self.discover.play_all_requested.connect(lambda songs: self._play_context(songs, 0))
        self.discover.download_requested.connect(self._start_download)
        self.discover.table.play_requested.connect(
            lambda s, row: self._play_context(self.discover.table.songs(), row))

        # 歌单页
        self.playlist_page.play_all_requested.connect(lambda songs: self._play_context(songs, 0))
        self.playlist_page.download_all_requested.connect(self._start_download)
        self.playlist_page.download_selected_requested.connect(self._start_download)
        self.playlist_page.export_requested.connect(self._export_playlist)
        self.playlist_page.table.play_requested.connect(
            lambda s, row: self._play_context(self.playlist_page.table.songs(), row))

        # 下载页
        self.download_page.retry_requested.connect(self._on_retry)
        self.download_page.cancel_requested.connect(self._on_cancel)
        self.download_page.cookie_requested.connect(self._open_cookie)
        self.download_page.proxy_requested.connect(self._open_proxy)
        self.download_page.dir_changed.connect(
            lambda d: (self.settings.set("save_dir", d), self.toast("保存目录已更新")))
        self.download_page.settings_changed.connect(self._save_download_settings)

        # 下载管理器
        self.manager.task_changed.connect(self.download_page.update_task)
        self.manager.finished_run.connect(self._on_download_finished)
        self.manager.log_line.connect(self._on_manager_log)

        # 播放器
        self.player.positionChanged.connect(self._on_position)
        self.player.stateChanged.connect(
            lambda st: self._update_play_button_state(st == QMediaPlayer.PlayingState))
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.error.connect(self._on_player_error)
        self.player.durationChanged.connect(self._on_duration_changed)

    # ================= 通用 =================
    def toast(self, text, ms=2200):
        self.toast_tip.show_message(text, ms)

    def run_async(self, fn, on_done, on_fail=None):
        """后台线程执行网络请求，结果经信号回主线程"""
        a = _Async(self)
        a.done.connect(on_done)
        if on_fail is not None:
            a.fail.connect(on_fail)
        else:
            a.fail.connect(lambda e: self.toast(f"请求失败：{e}"))

        def _worker():
            try:
                a.done.emit(fn())
            except Exception as e:
                a.fail.emit(str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _switch_page(self, idx):
        """切换主内容页面"""
        self.stack.setCurrentIndex(idx)
        
        # 更新导航按钮状态
        if hasattr(self, 'nav_buttons'):
            nav_key = None
            if idx == self.PAGE_DOWNLOAD:
                nav_key = "downloads"
            elif idx == self.PAGE_LOCAL:
                nav_key = "local"
            elif idx == self.PAGE_NOWPLAYING:
                nav_key = "nowplaying"
            else:
                nav_key = "discover"
            
            # 更新按钮状态（使用新逻辑）
            for key, btn in self.nav_buttons.items():
                btn.setChecked(key == nav_key)

    def _on_nav(self, key):
        """处理导航点击"""
        # 更新导航按钮状态
        if hasattr(self, 'nav_buttons'):
            for nav_key, btn in self.nav_buttons.items():
                btn.setChecked(nav_key == key)
        
        # 切换页面
        if key == "downloads":
            self._switch_page(self.PAGE_DOWNLOAD)
        elif key == "local":
            self._switch_page(self.PAGE_LOCAL)
        elif key == "nowplaying":
            self._switch_page(self.PAGE_NOWPLAYING)
        else:
            self._switch_page(self.PAGE_DISCOVER)

    # ================= 查询 / 解析 =================
    def on_query(self, text):
        text = (text or "").strip()
        if not text:
            self.toast("请输入歌单链接或搜索关键词")
            return
        proxy = self.settings.get("proxy")
        cookie = self.settings.get("cookie")
        kind, sid = api.parse_music_url(text)

        if kind == "playlist":
            self.toast("正在解析歌单…")
            self.run_async(lambda: api.fetch_playlist(sid, proxy, cookie),
                           self._open_playlist, self._fetch_fail)
        elif kind == "album":
            self.toast("正在解析专辑…")
            self.run_async(lambda: api.fetch_album(sid, proxy, cookie),
                           self._open_playlist, self._fetch_fail)
        elif kind == "song":
            self.toast("正在解析单曲…")
            self.run_async(lambda: api.fetch_song_detail(sid, proxy, cookie),
                           self._open_single, self._fetch_fail)
        else:
            self.toast(f"搜索“{text}”…")
            self.run_async(lambda: api.search_songs(text, 50, proxy, cookie),
                           self._show_search, self._fetch_fail)

    def _fetch_fail(self, msg):
        self.toast(f"获取失败：{msg}")

    def _show_search(self, songs):
        if not songs:
            self.toast("没有找到相关歌曲")
            return
        self.discover.set_results(songs)
        self._switch_page(self.PAGE_DISCOVER)

    def _open_single(self, song):
        if not song:
            self._fetch_fail("未找到该单曲")
            return
        pl = Playlist(id=str(song.id), kind="song", title=song.name,
                      creator=song.artist, songs=[song])
        self._open_playlist(pl)

    def _open_playlist(self, pl):
        if not pl or not pl.songs:
            self._fetch_fail("歌单为空或未公开")
            return
        self.playlist = pl
        self.playlist_page.set_playlist(pl)
        entry = (pl.kind, str(pl.id), pl.title)
        if entry not in self._pl_entries:
            self._pl_entries.append(entry)
            # 简化侧栏不含歌单条目列表
        self._async_cover(pl.cover_url, self.playlist_page.set_cover)
        self._switch_page(self.PAGE_PLAYLIST)

    def _on_sidebar_playlist(self, pid):
        entry = next((e for e in self._pl_entries if e[1] == str(pid)), None)
        if not entry:
            return
        kind, eid, _ = entry
        if self.playlist and self.playlist.kind == kind and str(self.playlist.id) == eid:
            self._switch_page(self.PAGE_PLAYLIST)
            return
        # 重新拉取该歌单/专辑/单曲
        text = f"{kind}?id={eid}"
        self.on_query(text)

    def _async_cover(self, url, on_done):
        """后台下载封面 → QPixmap 回调"""
        if not url:
            return
        proxy = self.settings.get("proxy")
        cookie = self.settings.get("cookie")

        def task():
            return api.download_cover_bytes(url, proxy, cookie)

        def done(data):
            if data:
                pm = QPixmap()
                if pm.loadFromData(data):
                    on_done(pm)

        self.run_async(task, done)

    # ================= 播放 =================
    def _play_context(self, songs, row):
        if not songs:
            return
        self.play_songs = list(songs)
        self.play_index = row if 0 <= row < len(songs) else 0
        self._play_current()

    def _play_current(self):
        if not self.play_songs or not (0 <= self.play_index < len(self.play_songs)):
            return
        song = self.play_songs[self.play_index]
        
        # 更新简化播放条的歌曲信息
        self.song_title.setText(song.name)
        self.song_artist.setText(song.artist)
        
        self.discover.table.set_playing(song.id)
        self.playlist_page.table.set_playing(song.id)
        self._sync_like_ui(song.id)
        self._async_cover_song(song)
        self.now_page.set_track(song.name, song.artist)

        # 本地曲库歌曲（id = "local:<文件路径>"）
        if str(song.id).startswith("local:"):
            path = str(song.id)[6:]
            self._now = {"kind": "local", "path": path, "song": None,
                         "title": song.name, "artist": song.artist}
            self._async_local_cover(path)
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
            self.player.play()
            self._load_lyrics()
            return

        self._now = {"kind": "online", "path": None, "song": song,
                     "title": song.name, "artist": song.artist}
        local = self._local_file(song)
        if local:
            self._now["path"] = str(local)
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(str(local))))
            self.player.play()
            self._load_lyrics()
            return

        cookie = self.settings.get("cookie")
        proxy = self.settings.get("proxy")
        # resolve_playable_url 会跟随 302 并校验音频魔数：
        # 返回最终直链；无版权歌（外链会 302 到 404 页）返回 None → 明确提示而不是播放器报模糊错误
        self.run_async(lambda: api.resolve_playable_url(song.id, 128000, proxy, cookie),
                       self._play_url, lambda e: self.toast(f"获取播放链接失败：{e}"))

    def _play_url(self, url):
        if not url:
            self.now_page.set_lyrics([], [], hint="该歌曲无版权 / 需要 VIP / Cookie，或音频已下架")
            self.toast("该歌曲无版权 / 需要 VIP / Cookie，或音频已下架，无法试听", 4000)
            return
        self.player.setMedia(QMediaContent(QUrl(url)))
        self.player.play()
        self._load_lyrics()

    # ================= 播放器回调 =================
    
    def _update_play_button_state(self, is_playing):
        """更新播放按钮状态"""
        from app.ui.icons import make_icon
        icon_name = "pause" if is_playing else "play"
        self.play_btn.setIcon(make_icon(icon_name, "#EC4141", 20))
    
    def _toggle_play(self):
        """切换播放/暂停"""
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()
    
    def _prev(self):
        """上一首"""
        self._step(-1)
    
    def _next(self):
        """下一首"""
        self._step(1)
    
    def _on_duration_changed(self, duration):
        """处理时长变化"""
        if duration > 0:
            self.progress_slider.setRange(0, duration)
            self.progress_slider.setEnabled(True)
            self.time_tot.setText(_fmt_ms(duration))
        else:
            self.progress_slider.setEnabled(False)
            self.time_tot.setText("00:00")

    def _on_position(self, pos):
        if hasattr(self, 'progress_slider'):
            if not self.progress_slider.is_dragging():
                self.progress_slider.blockSignals(True)
                self.progress_slider.setValue(pos)
                self.progress_slider.blockSignals(False)
            self.time_cur.setText(_fmt_ms(pos))
        self.now_page.set_position(pos)

    def _local_file(self, song):
        base = Path(self.settings.get("save_dir"))
        return base / f"{safe_filename(song.display)}.mp3"

    def _async_cover_song(self, song):
        proxy = self.settings.get("proxy")
        cookie = self.settings.get("cookie")

        def t1():
            return api.get_cover_url(song.id, proxy, cookie)

        self.run_async(t1, lambda url: self._async_cover(url, self._on_cover_pm))

    def _async_local_cover(self, path):
        """本地歌曲：读取内嵌封面"""
        self.run_async(lambda: local_library.read_cover_bytes(path), self._on_cover_bytes)

    def _on_cover_bytes(self, data):
        if not data:
            return
        pm = QPixmap()
        if pm.loadFromData(data):
            self._on_cover_pm(pm)

    def _on_cover_pm(self, pm):
        self.now_page.set_cover(pm)

    # ================= 歌词（字幕） =================
    def _load_lyrics(self):
        if self._loading_lyrics:
            return
        now = dict(self._now or {})
        title, artist = now.get("title", ""), now.get("artist", "")
        self.now_page.set_track(title, artist)
        self.now_page.set_lyrics([], [], hint="正在查找歌词…")
        self._lrc_plain_text, self._lrc_saved_path = "", ""
        self._loading_lyrics = True
        proxy = self.settings.get("proxy")
        cookie = self.settings.get("cookie")

        def task():
            # 1) 本地字幕识别：同名 .lrc（含 lyrics/lrc 子目录）
            path = now.get("path")
            if path:
                hit = lrc_io.find_local_lrc(path)
                if hit:
                    return {"text": lrc_io.load_lrc_text(hit), "save": None}
            # 2) 在线歌曲：直接按歌曲 id 取歌词，并缓存到保存目录
            if now.get("kind") == "online" and now.get("song") is not None:
                text = api.get_lyric(now["song"].id, proxy, cookie) or ""
                save = (str(Path(self.settings.get("save_dir")) /
                            f"{safe_filename(now['song'].display)}.lrc")) if text else None
                return {"text": text, "save": save}
            # 3) 本地曲库无字幕：按 标题+歌手 搜索网易云匹配
            for s in (api.search_songs(f"{title} {artist}".strip(), 3, proxy, cookie) or []):
                text = api.get_lyric(s.id, proxy, cookie) or ""
                if text and lrc_io._TIME_TAG.search(text):
                    save = str(Path(path).with_suffix(".lrc")) if path else None
                    return {"text": text, "save": save}
            return {"text": "", "save": None}

        def done(res):
            # 慢响应串台保护：结果不属于当前播放曲则丢弃
            if self._now and (self._now.get("title"), self._now.get("artist")) != (title, artist):
                self._loading_lyrics = False
                return
            text = (res or {}).get("text") or ""
            save = (res or {}).get("save")
            if not text:
                self.now_page.set_lyrics([], [], hint="暂无歌词（纯音乐或未收录）")
                self._loading_lyrics = False
                return
            self._lrc_plain_text = text
            if save:  # 自动下载/缓存字幕
                try:
                    lrc_io.save_lrc(save, text)
                    self._lrc_saved_path = save
                except Exception:
                    pass
            timed, plain = lrc_io.parse_lrc(text)
            self.now_page.set_lyrics(timed, plain)
            self._loading_lyrics = False

        def error_handler(e):
            self.now_page.set_lyrics([], [], hint=f"歌词获取失败：{e}")
            self._loading_lyrics = False

        self.run_async(task, done, error_handler)

    def _save_current_lrc(self):
        """手动保存当前歌词为 .lrc 字幕"""
        if not self._lrc_plain_text:
            self.toast("当前没有可保存的歌词")
            return
        if self._lrc_saved_path:
            self.toast(f"字幕已在此前保存：{self._lrc_saved_path}", 3000)
            return
        title = (self._now or {}).get("title") or "lyrics"
        p = lrc_io.save_lrc(Path(self.settings.get("save_dir")) /
                            f"{safe_filename(title)}.lrc", self._lrc_plain_text)
        self._lrc_saved_path = str(p)
        self.toast(f"已保存字幕：{p.name}")

    # ================= 本地音乐 =================
    def _play_local_tracks(self, tracks, row=0):
        if not tracks:
            self.toast("本地曲库为空，请先选择目录扫描")
            return
        songs = [Song(id=f"local:{t.path}", name=t.title, artist=t.artist,
                      album=t.album, duration_ms=t.duration_ms) for t in tracks]
        self._play_context(songs, row if 0 <= row < len(songs) else 0)

    def _on_local_dir_changed(self, d):
        self.settings.set("local_dir", d)
        self._rescan_local(d)

    def _rescan_local(self, d=None):
        d = d or self.settings.get("local_dir") or self.settings.get("save_dir")
        self.local_page.set_dir(str(d))
        self.toast(f"正在扫描本地音乐：{d}")
        self.run_async(lambda: local_library.scan_directory(str(d)),
                       self.local_page.set_tracks,
                       lambda e: self.toast(f"扫描失败：{e}"))

    def _fetch_lrc_for_track(self, track):
        """本地曲库：为选中歌曲匹配并下载 .lrc 字幕"""
        proxy = self.settings.get("proxy")
        cookie = self.settings.get("cookie")
        self.toast(f"正在为《{track.title}》匹配歌词…")

        def task():
            for s in (api.search_songs(f"{track.title} {track.artist}".strip(),
                                       3, proxy, cookie) or []):
                text = api.get_lyric(s.id, proxy, cookie) or ""
                if text and lrc_io._TIME_TAG.search(text):
                    save = str(Path(track.path).with_suffix(".lrc"))
                    lrc_io.save_lrc(save, text)
                    return {"path": track.path, "ok": True}
            return {"path": track.path, "ok": False}

        def done(res):
            if res.get("ok"):
                self.toast("歌词（字幕）已下载")
                t = next((t for t in self.local_page.tracks if t.path == res["path"]), None)
                if t:
                    t.has_lrc = True
                self.local_page.refresh_lrc_state(res["path"])
            else:
                self.toast("未在网易云匹配到该歌的歌词")

        self.run_async(task, done)

    def _on_play_toggle(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            return
        if self.player.media().isNull():
            if self.play_songs:
                self._play_current()
            return
        self.player.play()

    def _step(self, direction):
        n = len(self.play_songs)
        if not n:
            return
        if self.mode == "shuffle" and n > 1:
            idx = self.play_index
            while idx == self.play_index:
                idx = random.randrange(n)
            self.play_index = idx
        else:
            self.play_index = (self.play_index + direction) % n
        self._play_current()

    def _on_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self._step(1)

    def _on_player_error(self, _err):
        media = self.player.media()
        if media is None or media.isNull():
            return
        if _err == QMediaPlayer.ServiceMissingError:
            self.toast("播放失败：系统缺少 Qt 媒体后端，请执行 "
                       "sudo apt install libqt5multimedia5-plugins 后重启应用"
                       "（下载功能不受影响）", 5000)
            return
        msg = self.player.errorString()
        if msg:
            self.toast(f"试听失败：{msg}（可能需要 VIP / Cookie），可下载后播放", 3000)

    def _on_mode_changed(self, mode):
        self.mode = mode
        self.toast("随机播放" if mode == "shuffle" else "列表循环")

    def _sync_like_ui(self, song_id):
        liked = str(song_id) in [str(x) for x in self.settings.get("liked", [])]
        # 简化播放条不含喜欢按钮
        return

    def _on_like_toggled(self, liked):
        if not (0 <= self.play_index < len(self.play_songs)):
            return
        sid = str(self.play_songs[self.play_index].id)
        ids = [str(x) for x in self.settings.get("liked", [])]
        if liked and sid not in ids:
            ids.append(sid)
        elif not liked and sid in ids:
            ids.remove(sid)
        self.settings.set("liked", ids)
        self.toast("已加入喜欢的音乐" if liked else "已取消喜欢")

    # ================= 下载 =================
    def _start_download(self, songs):
        if not songs:
            self.toast("请先选择歌曲")
            return
        if self.manager.is_busy():
            self.toast("已有下载任务进行中，请等待完成或取消")
            return
        self.manager.setup(
            songs,
            self.settings.get("save_dir"),
            self.download_page.get_quality(),
            self.download_page.get_workers(),
            self.download_page.get_retries(),
            self.settings.get("proxy"),
            self.settings.get("cookie"),
            self.download_page.get_embed(),
        )
        self.download_page.set_tasks(songs)
        self.download_page.set_busy(True)
        self.download_page.set_status("下载中…")
        self._switch_page(self.PAGE_DOWNLOAD)
        self.manager.start()

    def _on_retry(self):
        if self.manager.is_busy():
            return
        if not self.manager.failed:
            self.toast("没有失败的任务")
            return
        self._start_download(list(self.manager.failed))

    def _on_cancel(self):
        if self.manager.is_busy():
            self.manager.cancel()
            self.download_page.set_status("取消中…")
            self.toast("正在取消下载…")

    def _on_download_finished(self, all_ok):
        self.download_page.set_busy(False)
        failed = len(self.manager.failed)
        if failed:
            self.download_page.set_status(f"完成，失败 {failed} 首")
            self.toast(f"下载完成，失败 {failed} 首，可点击重试失败")
        else:
            self.download_page.set_status("全部完成")
            self.toast("下载完成")
        if all_ok and self.settings.get("auto_open", False):
            self._open_local_dir()

    def _on_manager_log(self, msg, level):
        if level == "error":
            self.toast(f"下载出错：{msg}")

    def _save_download_settings(self):
        self.settings.set("quality", self.download_page.get_quality())
        self.settings.set("workers", self.download_page.get_workers())
        self.settings.set("retries", self.download_page.get_retries())
        self.settings.set("embed_cover", self.download_page.get_embed())

    # ================= 设置 / 工具 =================
    def _open_cookie(self):
        dlg = CookieDialog(self.settings.get("cookie", ""), self)
        if dlg.exec_() == QDialog.Accepted:
            cookie = dlg.get_cookie()
            self.settings.set("cookie", cookie)
            self.toast("Cookie 已保存" if cookie else "Cookie 已清除")

    def _open_proxy(self):
        dlg = ProxyDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            p = dlg.get_proxy_dict()
            self.settings.set("proxy", p)
            self.toast("代理已启用" if p else "代理已禁用")


    def _open_local_dir(self):
        d = self.settings.get("local_dir") or self.settings.get("save_dir")
        p = Path(d)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
        except Exception:
            # 离屏/无桌面环境或 openDocument 未实现时静默降级
            self.toast(f"本地音乐目录：{p}")

    def _export_playlist(self):
        if not self.playlist or not self.playlist.songs:
            self.toast("当前没有可导出的歌单")
            return
        default = f"{self.playlist.title or 'playlist'}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出歌单", default, "JSON (*.json);;CSV (*.csv);;TXT (*.txt)")
        if not path:
            return
        try:
            export_songs(self.playlist.songs, path)
            self.toast(f"已导出 {len(self.playlist.songs)} 首")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _import_playlist(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入歌单", "", "歌单文件 (*.json *.csv *.txt)")
        if not path:
            return
        try:
            songs = import_songs(path)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return
        if not songs:
            self.toast("未解析到有效歌曲")
            return
        self.discover.set_results(songs)
        self._switch_page(self.PAGE_DISCOVER)
        self.toast(f"已导入 {len(songs)} 首")

    def closeEvent(self, ev):
        if self.manager.is_busy():
            r = QMessageBox.question(self, "退出确认", "下载正在进行，确定退出吗？",
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                ev.ignore()
                return
            self.manager.cancel()
            self.manager.wait(3000)
        ev.accept()


def _app_icon():
    from app.ui.icons import app_icon
    return app_icon()
