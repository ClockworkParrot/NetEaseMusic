# -*- coding: utf-8 -*-
"""主窗口：顶栏 + 侧边栏 + 三个页面 + 底部播放条 的组装与业务编排"""
import random
import threading
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QDesktopServices
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QFileDialog, QMessageBox, QDialog,
                             QApplication)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

from app.core import api
from app.core.models import Playlist
from app.core.downloader import DownloadManager, safe_filename
from app.core.playlist_io import export_songs, import_songs
from app.ui.theme import build_qss, LIGHT, DARK
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.titlebar import TitleBar
from app.ui.widgets.player_bar import PlayerBar
from app.ui.widgets.toast import Toast
from app.ui.dialogs import CookieDialog, ProxyDialog
from app.ui.pages.discover_page import DiscoverPage
from app.ui.pages.playlist_page import PlaylistPage
from app.ui.pages.download_page import DownloadPage


class _Async(QObject):
    """线程池任务的完成/失败信号（跨线程安全投递到主线程）"""
    done = pyqtSignal(object)
    fail = pyqtSignal(str)


class MainWindow(QMainWindow):
    PAGE_DISCOVER, PAGE_PLAYLIST, PAGE_DOWNLOAD = 0, 1, 2

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

        self.setWindowTitle("网易云音乐下载器")
        self.setWindowIcon(_app_icon())
        self.resize(1160, 760)
        self.setMinimumSize(960, 640)

        self._build_ui()
        self._connect()

        # 应用保存的偏好
        vol = int(self.settings.get("volume", 70))
        self.player.setVolume(vol)
        self.player_bar.set_volume(vol)
        self.download_page.set_dir(self.settings.get("save_dir"))
        self.download_page.set_quality(int(self.settings.get("quality", 192000)))
        self.download_page.set_workers(int(self.settings.get("workers", 3)))
        self.download_page.set_retries(int(self.settings.get("retries", 3)))
        self.download_page.set_embed(bool(self.settings.get("embed_cover", True)))
        self.titlebar.set_dark(self._dark)
        self.sidebar.set_playlists([])

    # ================= UI 构建 =================
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.titlebar = TitleBar()
        outer.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar()
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.discover = DiscoverPage()
        self.playlist_page = PlaylistPage()
        self.download_page = DownloadPage()
        self.stack.addWidget(self.discover)
        self.stack.addWidget(self.playlist_page)
        self.stack.addWidget(self.download_page)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self.player_bar = PlayerBar()
        outer.addWidget(self.player_bar)

        self.toast_tip = Toast(root)

    def _connect(self):
        # 顶栏
        self.titlebar.search_submitted.connect(self.on_query)
        self.titlebar.theme_toggled.connect(self._toggle_theme)
        self.titlebar.cookie_requested.connect(self._open_cookie)
        self.titlebar.proxy_requested.connect(self._open_proxy)

        # 侧栏
        self.sidebar.navigate.connect(self._on_nav)
        self.sidebar.open_local.connect(self._open_local_dir)
        self.sidebar.playlist_clicked.connect(self._on_sidebar_playlist)

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
        self.player.positionChanged.connect(
            lambda pos: self.player_bar.set_position(pos, self.player.duration()))
        self.player.durationChanged.connect(
            lambda dur: self.player_bar.set_position(self.player.position(), dur))
        self.player.stateChanged.connect(
            lambda st: self.player_bar.set_playing(st == QMediaPlayer.PlayingState))
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.error.connect(self._on_player_error)

        # 播放条
        self.player_bar.play_toggled.connect(self._on_play_toggle)
        self.player_bar.prev_clicked.connect(lambda: self._step(-1))
        self.player_bar.next_clicked.connect(lambda: self._step(1))
        self.player_bar.seek_requested.connect(self.player.setPosition)
        self.player_bar.volume_changed.connect(self.player.setVolume)
        self.player_bar.volume.sliderReleased.connect(
            lambda: self.settings.set("volume", self.player_bar.volume.value()))
        self.player_bar.mode_changed.connect(self._on_mode_changed)
        self.player_bar.like_toggled.connect(self._on_like_toggled)
        self.player_bar.open_downloads.connect(lambda: self._switch_page(self.PAGE_DOWNLOAD))

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
        self.stack.setCurrentIndex(idx)
        if idx == self.PAGE_DOWNLOAD:
            self.sidebar.set_checked("downloads")
        else:
            self.sidebar.set_checked("discover")

    def _on_nav(self, key):
        if key == "downloads":
            self._switch_page(self.PAGE_DOWNLOAD)
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
            self.sidebar.set_playlists([(e[1], e[2]) for e in self._pl_entries])
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
        self.player_bar.set_song(song)
        self.discover.table.set_playing(song.id)
        self.playlist_page.table.set_playing(song.id)
        self._sync_like_ui(song.id)
        self._async_cover_song(song)

        local = self._local_file(song)
        if local:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(str(local))))
            self.player.play()
            return

        cookie = self.settings.get("cookie")
        proxy = self.settings.get("proxy")
        # resolve_playable_url 会跟随 302 并校验音频魔数：
        # 返回最终直链；无版权歌（外链会 302 到 404 页）返回 None → 明确提示而不是播放器报模糊错误
        self.run_async(lambda: api.resolve_playable_url(song.id, 128000, proxy, cookie),
                       self._play_url, lambda e: self.toast(f"获取播放链接失败：{e}"))

    def _play_url(self, url):
        if not url:
            self.toast("该歌曲无版权或需要 VIP / Cookie，无法试听（可下载后播放）", 4000)
            return
        self.player.setMedia(QMediaContent(QUrl(url)))
        self.player.play()

    def _local_file(self, song):
        base = Path(self.settings.get("save_dir"))
        return base / f"{safe_filename(song.display)}.mp3"

    def _async_cover_song(self, song):
        proxy = self.settings.get("proxy")
        cookie = self.settings.get("cookie")

        def t1():
            return api.get_cover_url(song.id, proxy, cookie)

        self.run_async(t1, lambda url: self._async_cover(url, self.player_bar.set_cover))

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
        self.player_bar.set_liked(liked)

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

    def _toggle_theme(self):
        self._dark = not self._dark
        QApplication.instance().setStyleSheet(build_qss(DARK if self._dark else LIGHT))
        self.settings.set("dark", self._dark)
        self.titlebar.set_dark(self._dark)

    def _open_local_dir(self):
        p = Path(self.settings.get("save_dir"))
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

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
        self.settings.save()
        ev.accept()


def _app_icon():
    from app.ui.icons import app_icon
    return app_icon()
