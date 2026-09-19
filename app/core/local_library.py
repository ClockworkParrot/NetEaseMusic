# -*- coding: utf-8 -*-
"""本地音乐扫描识别：读取音频标签构建曲库（mutagen 优先，退化用文件名解析）"""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except Exception:
    HAS_MUTAGEN = False

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".wav", ".ogg", ".ape", ".wma"}


@dataclass
class LocalTrack:
    """本地曲库中的一首歌"""
    path: str
    title: str
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    size: int = 0
    has_lrc: bool = False

    @property
    def display(self) -> str:
        return f"{self.title} - {self.artist}" if self.artist else self.title

    @property
    def duration_text(self) -> str:
        if self.duration_ms <= 0:
            return "--:--"
        s = self.duration_ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"


def read_track(p):
    """识别单个音频文件：优先 mutagen 标签，缺标签时按 '歌手 - 歌名' 文件名解析。
    不存在或零字节（未下载完/已删除）的文件不入曲库。"""
    p = Path(p)
    try:
        size = p.stat().st_size
    except OSError:
        return None
    if size == 0:
        return None
    title, artist, album = p.stem, "", ""
    if " - " in p.stem:
        a, _, b = p.stem.partition(" - ")
        artist, title = a.strip(), b.strip()
    duration_ms = 0
    if HAS_MUTAGEN:
        try:
            mf = MutagenFile(str(p), easy=True)
            if mf is not None:
                duration_ms = int(getattr(mf.info, "length", 0) * 1000)
                if duration_ms <= 0:
                    # 仅头部的残缺文件（ID3-only、零帧 mp3 等）无法播放，不入曲库
                    return None

                def g(tag):
                    v = (mf.get(tag) or [""])[0]
                    return str(v).strip()

                title = g("title") or title
                artist = g("artist") or artist
                album = g("album") or album
        except Exception:
            return None
    if not title:
        return None
    return LocalTrack(str(p), title, artist, album, duration_ms, size)


def read_cover_bytes(path):
    """读取音频文件内嵌封面的二进制数据，无则 None。
    支持 ID3 APIC(mp3) / FLAC METADATA_BLOCK_PICTURE / MP4 covr(m4a)。"""
    if not HAS_MUTAGEN:
        return None
    try:
        import base64
        mf = MutagenFile(str(path))
        if mf is None or not getattr(mf, "tags", None):
            return None
        # ID3（mp3）：APIC 帧
        try:
            pics = mf.tags.getall("APIC")
            if pics:
                return pics[0].data
        except Exception:
            pass
        # FLAC：优先用高层 pictures()，失败则解码 base64 的 METADATA_BLOCK_PICTURE
        try:
            pics = getattr(mf, "pictures", None)
            if callable(pics):
                plist = pics()
                if plist:
                    return plist[0].data
        except Exception:
            pass
        try:
            raw = mf.tags.getall("METADATA_BLOCK_PICTURE")
            if raw:
                from mutagen.flac import Picture
                pic = Picture(base64.b64decode(raw[0] if isinstance(raw[0], str)
                                                else raw[0]))
                return pic.data
        except Exception:
            pass
        # MP4（m4a/mp4）：covr atom
        try:
            covr = mf.tags.get("covr")
            if covr:
                return bytes(covr[0])
        except Exception:
            pass
        return None
    except Exception:
        return None


def scan_directory(root):
    """递归扫描目录下的音频文件 → [LocalTrack]，并识别每个文件的同名 .lrc 字幕"""
    from app.core.lyrics import find_local_lrc

    root = Path(root)
    out = []
    if not root.exists():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            if Path(fn).suffix.lower() not in AUDIO_EXTS:
                continue
            t = read_track(Path(dirpath) / fn)
            if t:
                t.has_lrc = find_local_lrc(t.path) is not None
                out.append(t)
    return out
