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
    """识别单个音频文件：优先 mutagen 标签，缺标签时按 '歌手 - 歌名' 文件名解析"""
    p = Path(p)
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

                def g(tag):
                    v = (mf.get(tag) or [""])[0]
                    return str(v).strip()

                title = g("title") or title
                artist = g("artist") or artist
                album = g("album") or album
        except Exception:
            pass
    if not title:
        return None
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return LocalTrack(str(p), title, artist, album, duration_ms, size)


def read_cover_bytes(path):
    """读取音频文件内嵌封面（ID3 APIC 等）的二进制数据，无则 None"""
    if not HAS_MUTAGEN:
        return None
    try:
        mf = MutagenFile(str(path))
        if mf is None or not mf.tags:
            return None
        pics = mf.tags.getall("APIC")
        if pics:
            return pics[0].data
        pics = mf.tags.getall("METADATA_BLOCK_PICTURE")  # flac
        return pics[0].data if pics else None
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
