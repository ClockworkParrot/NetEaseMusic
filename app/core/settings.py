# -*- coding: utf-8 -*-
"""JSON 设置持久化（替代原项目的 QSettings，跨平台且可读）"""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".netease_music"
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULTS = {
    "cookie": "",                                   # 网易云 Cookie（含 MUSIC_U 可提升音质权限）
    "save_dir": str(Path.home() / "Music" / "NetEaseDownload"),
    "quality": 192000,                              # 128000 / 192000 / 320000
    "workers": 3,                                   # 并发下载数
    "retries": 3,                                   # 单文件下载重试次数
    "embed_cover": True,                            # 下载后嵌入封面
    "auto_open": False,                             # 完成后打开目录
    "dark": False,                                  # 深色主题
    "volume": 70,                                   # 播放器音量
    "liked": [],                                    # 本地标记喜欢的歌曲 id
    "proxy": None,                                  # {"http": ..., "https": ...}
}


class AppSettings:
    """简单的键值设置读写，写入 ~/.netease_music/settings.json"""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    if k in DEFAULTS:
                        self._data[k] = v
        except Exception:
            pass  # 配置损坏时静默使用默认值

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self._data[key] = value
        self.save()
