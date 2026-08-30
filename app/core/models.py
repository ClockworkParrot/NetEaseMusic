# -*- coding: utf-8 -*-
"""数据模型：歌曲与歌单"""
from dataclasses import dataclass, field


@dataclass
class Song:
    """一首歌曲：网易云 ID、名称、歌手、专辑、时长(ms)"""
    id: str
    name: str
    artist: str = ""
    album: str = ""
    duration_ms: int = 0

    @property
    def display(self) -> str:
        """用于文件名/展示的 '歌名 - 歌手' 形式"""
        return f"{self.name} - {self.artist}" if self.artist else self.name

    @property
    def duration_text(self) -> str:
        """时长文本 mm:ss"""
        if self.duration_ms <= 0:
            return "--:--"
        s = self.duration_ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"


@dataclass
class Playlist:
    """歌单 / 专辑 / 单曲集合的统一容器"""
    id: str = ""
    kind: str = "playlist"      # playlist / album / song
    title: str = ""
    creator: str = ""
    cover_url: str = ""
    songs: list = field(default_factory=list)
