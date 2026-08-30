# -*- coding: utf-8 -*-
"""下载管理：QThread + 线程池，支持取消、失败重试、单文件实时进度。"""
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from app.core import api

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
    HAS_MUTAGEN = True
except Exception:
    HAS_MUTAGEN = False

# 任务状态（download_page 依据这些值渲染颜色与文本）
ST_WAIT, ST_RUN, ST_DONE, ST_FAIL, ST_EXISTS = "wait", "run", "done", "fail", "exists"


def safe_filename(text, max_len=80):
    """将歌曲名转换为安全的文件名（Windows 非法字符替换）"""
    text = re.sub(r'[\\/*"<>|]', " ", text)
    text = text.replace(":", "：").replace("?", "？").replace("\n", " ").replace("\r", " ")
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text.strip()


def _embed_cover(mp3_path, cover_bytes, title, artist, album):
    """通过 mutagen 将封面/标题/歌手/专辑写入 ID3 标签。

    - 只接受 JPEG/PNG 图片（其余数据播放器无法解码，直接拒绝）
    - 以 ID3v2.3 保存：Windows 资源管理器与大多数播放器对默认的 v2.4 兼容差，
      表现为“嵌入了但看不到封面”
    - 返回是否成功，由调用方记录日志（不再静默吞掉失败）
    """
    if cover_bytes[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif cover_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    else:
        return False
    try:
        audio = MP3(str(mp3_path), ID3=ID3)
        try:
            audio.add_tags()   # 无标签文件补建；已存在则忽略
        except Exception:
            pass
        audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover_bytes))
        if title:
            audio.tags.add(TIT2(encoding=3, text=title))
        if artist:
            audio.tags.add(TPE1(encoding=3, text=artist))
        if album:
            audio.tags.add(TALB(encoding=3, text=album))
        audio.save(v2_version=3)
        return True
    except Exception:
        return False


class DownloadManager(QThread):
    """一次 run() 处理一批任务；每首歌状态变化通过 task_changed 信号回传 UI。

    外部流程：
        manager.setup(songs, dir, br, workers, proxy, cookie, embed_cover)
        manager.start()  ->  task_changed(...) * N  ->  finished_run(bool)
    """

    task_changed = pyqtSignal(str, str, int, str)   # song_id, state, percent, message
    log_line = pyqtSignal(str, str)                 # message, level(info/warn/error)
    finished_run = pyqtSignal(bool)                 # True=全部成功且未取消

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []                  # list[Song]
        self.save_dir = Path("./download")
        self.br = 192000
        self.max_workers = 3
        self.retries = 3
        self.proxy = None
        self.cookie = ""
        self.embed_cover = True
        self.failed = []                 # list[Song] 供重试
        self._cancel = threading.Event()

    # ---------- 外部 API ----------
    def setup(self, songs, save_dir, br, workers, retries, proxy, cookie, embed_cover):
        self.queue = list(songs)
        self.save_dir = Path(save_dir)
        self.br = int(br)
        self.max_workers = max(1, min(8, int(workers)))
        self.retries = max(1, min(10, int(retries)))
        self.proxy = proxy
        self.cookie = cookie or ""
        self.embed_cover = bool(embed_cover)
        self.failed = []
        self._cancel.clear()

    def cancel(self):
        self._cancel.set()

    def is_busy(self):
        return self.isRunning()

    # ---------- 线程主体 ----------
    def run(self):
        if not self.queue:
            self.finished_run.emit(True)
            return
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_line.emit(f"创建保存目录失败: {e}", "error")
            self.finished_run.emit(False)
            return

        total = len(self.queue)
        ok_count = 0
        self.log_line.emit(f"开始下载 {total} 首（音质 {self.br // 1000}k，并发 {self.max_workers}）", "info")
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._download_one, song): song for song in self.queue}
            for fut in as_completed(futures):
                song = futures[fut]
                try:
                    ok = bool(fut.result())
                except Exception as e:
                    ok = False
                    self.task_changed.emit(song.id, ST_FAIL, 0, f"异常: {e}")
                if ok:
                    ok_count += 1
                elif not self._cancel.is_set():
                    self.failed.append(song)

        if self._cancel.is_set():
            # 每个任务内部会自查取消标志并回报“已取消”，此处无需覆盖状态
            self.log_line.emit("下载已取消", "warn")
            self.finished_run.emit(False)
        else:
            self.log_line.emit(f"本批完成：成功 {ok_count}/{total}", "info")
            self.finished_run.emit(len(self.failed) == 0)

    # ---------- 单个任务 ----------
    def _emit(self, song, state, pct=0, msg=""):
        self.task_changed.emit(song.id, state, int(pct), msg)

    def _download_one(self, song):
        if self._cancel.is_set():
            self._emit(song, ST_FAIL, 0, "已取消")
            return False

        safe = safe_filename(song.display)
        mp3_path = self.save_dir / f"{safe}.mp3"
        if mp3_path.exists() and mp3_path.stat().st_size > 0:
            self._emit(song, ST_EXISTS, 100, "已存在，跳过")
            return True

        self._emit(song, ST_RUN, 0, "获取链接…")
        # 单请求流式下载：open_audio_stream 深检通过后直接复用同一响应续写，
        # 避免 probe 与下载两次 GET 拿到不同内容（CDN 重复请求可能给占位假文件）
        ok, msg = False, ""
        for _ in range(1, self.retries + 1):
            if self._cancel.is_set():
                return False
            resp, head_buf = api.open_audio_stream(song.id, self.br, self.proxy, self.cookie)
            if not resp:
                ok, msg = False, "无版权或需要 VIP/Cookie（音频可能已下架）"
                break
            try:
                ok, msg = self._stream(song, resp, head_buf, mp3_path)
            finally:
                resp.close()
            if ok and not self._validate_saved(mp3_path):
                ok, msg = False, "源音频为空（歌曲可能已下架）"
            if ok or self._cancel.is_set():
                break
            time.sleep(1.5)
        if not ok:
            if mp3_path.exists():
                try:
                    mp3_path.unlink()
                except Exception:
                    pass
            self._emit(song, ST_FAIL, 0, msg or "下载失败")
            return False

        # 歌词
        lrc = api.get_lyric(song.id, self.proxy, self.cookie)
        if lrc:
            try:
                (self.save_dir / f"{safe}.lrc").write_text(lrc, encoding="utf-8")
            except Exception:
                pass

        # 封面嵌入
        if self.embed_cover and HAS_MUTAGEN:
            cover_url = api.get_cover_url(song.id, self.proxy, self.cookie)
            data = api.download_cover_bytes(cover_url, self.proxy, self.cookie) if cover_url else None
            if data and _embed_cover(mp3_path, data, song.name, song.artist, song.album):
                pass
            else:
                why = "未获取到封面链接" if not cover_url else (
                    "封面下载失败" if not data else "文件或图片无效，嵌入被跳过")
                self.log_line.emit(f"{song.display}: {why}", "warn")

        self._emit(song, ST_DONE, 100, "完成")
        return True

    def _stream(self, song, resp, head_buf, path):
        """单请求流式下载：先写入深检时预读的 head_buf（前 256KB，同一响应连接），
        再继续读 resp 剩余数据。Content-Length 可知时每 2% 回传进度。"""
        try:
            total = int(resp.headers.get("Content-Length") or 0)
            done, last_pct = 0, 0
            with open(path, "wb") as f:
                f.write(head_buf)
                done = len(head_buf)
                for chunk in resp.iter_content(8192):
                    if self._cancel.is_set():
                        return False, "已取消"
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = int(done * 100 / total)
                        if pct - last_pct >= 2:
                            last_pct = pct
                            self._emit(song, ST_RUN, pct, f"下载中 {pct}%")
            return True, ""
        except Exception as e:
            return False, str(e) or "网络错误"

    def _validate_saved(self, path):
        """下载完成后复核文件头 256KB：拦下“合法头+全零 payload”的占位假音频
        （probe 与下载是两次独立请求，CDN 内容可能不一致）。假文件删除并返回 False"""
        try:
            with open(path, "rb") as f:
                buf = f.read(256 * 1024)
            if api._is_audio_head(buf) and not api._audio_payload_ok(buf):
                os.remove(path)
                return False
            return True
        except Exception:
            return True  # 校验本身出错时不误伤正常文件
