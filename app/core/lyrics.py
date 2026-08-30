# -*- coding: utf-8 -*-
"""LRC 歌词（字幕）：解析、本地识别匹配、保存。支持多时间戳行与 [offset] 全局偏移"""
import re
from pathlib import Path

_TIME_TAG = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_OFFSET_TAG = re.compile(r"\[offset:\s*(-?\d+)\s*\]", re.IGNORECASE)


def parse_lrc(text):
    """解析 LRC 文本 → (timed, plain)

    timed: [(time_ms, line), ...] 按时间升序；plain: 无时间戳的纯文本行列表
    """
    timed, plain = [], []
    offset = 0
    m = _OFFSET_TAG.search(text)
    if m:
        try:
            offset = int(m.group(1))
        except ValueError:
            offset = 0
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        stamps = _TIME_TAG.findall(raw)
        content = _TIME_TAG.sub("", raw).strip()
        if not stamps:
            if content and not raw.startswith("["):
                plain.append(content)
            continue
        for mm, ss, frac in stamps:
            ms = (int(mm) * 60 + int(ss)) * 1000
            if frac:
                ms += int(frac[:3].ljust(3, "0"))
            timed.append((max(ms - offset, 0), content))
    timed.sort(key=lambda x: x[0])
    return timed, plain


def find_local_lrc(audio_path):
    """识别与音频文件关联的本地字幕：同目录同名 .lrc（含常见变体名）"""
    p = Path(audio_path)
    candidates = [
        p.with_suffix(".lrc"),
        p.parent / f"{p.stem}.lrc",
        p.parent / "lyrics" / f"{p.stem}.lrc",
        p.parent / "lrc" / f"{p.stem}.lrc",
    ]
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def load_lrc_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return Path(path).read_text(encoding="gb18030", errors="replace")
        except Exception:
            return ""


def save_lrc(path, text):
    """保存 LRC 文本到指定路径（下载字幕）"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def index_for_time(timed, ms):
    """二分查找 ms 时刻应高亮的歌词行下标（-1 表示尚未开始）"""
    if not timed:
        return -1
    lo, hi, ans = 0, len(timed) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if timed[mid][0] <= ms:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return ans
