# -*- coding: utf-8 -*-
"""网易云音乐公开 API 封装。

沿用原项目可用的端点（playlist/detail、song/detail、enhance/player/url、song/lyric），
新增：关键词搜索(search/get/web)、专辑详情(/api/album/{id})。
原版 Bug 修复：统一 (id, br, proxy, cookie) 参数签名，下载不再 TypeError。
"""
import re

import requests

from app.core.models import Song, Playlist

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://music.163.com/",
    "Cookie": "os=pc;",
}
# 直链源（resolve_playable_url 按优先级逐个尝试，全部经魔数校验）：
# 1. 官方 API enhance/player/url（音质/版权取决于 Cookie）
# 2. 官方外链 outer/url（免费歌 302→真实 mp3；无版权歌 302→404 页，校验可识别）
# 3. 第三方聚合源 link.hhtjim.com（对“API 不给非会员 url 但确有低音质试听”的歌有效；
#    仅对真无版权的歌返回 500 JSON，同样靠校验识别）

QUALITY_LIST = [(128000, "标准 (128k)"), (192000, "较高 (192k)"), (320000, "极高 (320k)")]


def _headers(cookie=None):
    h = DEFAULT_HEADERS.copy()
    if cookie:
        h["Cookie"] = cookie
    return h


def _get(url, proxy=None, cookie=None, timeout=10, params=None):
    return requests.get(url, headers=_headers(cookie), params=params,
                        proxies=proxy, timeout=timeout)


def _artist_text(artists):
    if not artists:
        return ""
    return "/".join(a.get("name", "") for a in artists if a.get("name"))


def _song_from_track(t):
    """兼容 v1(artists/album/duration) 与 v3(ar/al/dt) 两种字段结构"""
    return Song(
        id=str(t.get("id", "")),
        name=(t.get("name") or "").strip(),
        artist=_artist_text(t.get("artists") or t.get("ar") or []),
        album=((t.get("album") or t.get("al") or {}).get("name") or "").strip(),
        duration_ms=int(t.get("duration") or t.get("dt") or 0),
    )


def parse_music_url(text):
    """解析输入文本 → (kind, id)。

    支持: playlist/album/song 链接、?id= 链接、纯数字 ID（按单曲处理）。
    无法识别返回 (None, None)。
    """
    t = (text or "").strip().replace("/#/", "/").replace("/#", "/")
    m = re.search(r"(playlist|album|song)[=/](\d+)", t)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"[?&]id=(\d+)", t)
    if m:
        if "album" in t:
            return "album", m.group(1)
        if "song" in t:
            return "song", m.group(1)
        return "playlist", m.group(1)
    if re.fullmatch(r"\d+", t):
        return "song", t
    return None, None


def search_songs(keyword, limit=50, proxy=None, cookie=None):
    """关键词搜索歌曲 → list[Song]"""
    url = "https://music.163.com/api/search/get/web"
    params = {"s": keyword, "type": 1, "offset": 0, "limit": limit, "total": "true"}
    data = _get(url, proxy, cookie, timeout=15, params=params).json()
    songs = []
    for t in (data.get("result") or {}).get("songs") or []:
        s = _song_from_track(t)
        if s.id and s.name:
            songs.append(s)
    return songs


def fetch_playlist(pid, proxy=None, cookie=None):
    """歌单详情 → Playlist"""
    data = _get(f"https://music.163.com/api/playlist/detail?id={pid}",
                proxy, cookie, timeout=15).json()
    r = data.get("result") or {}
    songs = []
    for t in r.get("tracks") or []:
        s = _song_from_track(t)
        if s.id and s.name:
            songs.append(s)
    return Playlist(
        id=str(pid), kind="playlist",
        title=(r.get("name") or "").strip(),
        creator=(r.get("creator") or {}).get("nickname", ""),
        cover_url=r.get("coverImgUrl", ""),
        songs=songs,
    )


def fetch_album(aid, proxy=None, cookie=None):
    """专辑详情 → Playlist(kind=album)"""
    data = _get(f"https://music.163.com/api/album/{aid}", proxy, cookie, timeout=15).json()
    a = data.get("album") or {}
    songs = []
    for t in a.get("songs") or []:
        s = _song_from_track(t)
        if s.id and s.name:
            songs.append(s)
    return Playlist(
        id=str(aid), kind="album",
        title=(a.get("name") or "").strip(),
        creator=(a.get("artist") or {}).get("name", ""),
        cover_url=a.get("picUrl", ""),
        songs=songs,
    )


def fetch_song_detail(sid, proxy=None, cookie=None):
    """单曲详情 → Song 或 None"""
    try:
        data = _get(f"https://music.163.com/api/song/detail/?id={sid}&ids=[{sid}]",
                    proxy, cookie, timeout=10).json()
        arr = data.get("songs") or []
        return _song_from_track(arr[0]) if arr else None
    except Exception:
        return None


_MP3_MAGIC = (b"ID3",)  # 其余用 0xFFE0 掩码判断


def _is_audio_head(head):
    """判断响应头部字节是否为 MP3 音频（ID3 标签头或 MPEG 帧同步）"""
    if head[:3] == b"ID3":
        return True
    return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0


def _probe_audio_url(url, proxy=None, cookie=None):
    """GET url（跟随 302），首 4 字节为 MP3 魔数则返回最终直链，否则 None"""
    try:
        r = requests.get(url, headers=_headers(cookie), stream=True,
                         timeout=15, proxies=proxy, allow_redirects=True)
        head = r.raw.read(4, decode_content=True)
        final, ok = r.url, _is_audio_head(head)
        r.close()
        return final if ok else None
    except Exception:
        return None


def resolve_playable_url(sid, br=192000, proxy=None, cookie=None):
    """获取【已验证】的可播放/下载直链。

    按优先级尝试多个直链源（见文件头注释），每个源都跟随 302 并校验
    音频魔数，返回首个有效的最终直链；全部无效（真无版权）返回 None。
    """
    candidates = []
    # 1) 官方 API 直链
    try:
        data = _get("https://music.163.com/api/song/enhance/player/url",
                    proxy, cookie, params={"ids": f"[{sid}]", "br": br}).json()
        if data.get("code") == 200 and data.get("data"):
            u = data["data"][0].get("url")
            if u:
                candidates.append(u)
    except Exception:
        pass
    # 2) 官方外链  3) 第三方聚合源
    candidates.append(f"https://music.163.com/song/media/outer/url?id={sid}.mp3")
    candidates.append(f"https://link.hhtjim.com/163/{sid}.mp3")

    for cand in candidates:
        final = _probe_audio_url(cand, proxy, cookie)
        if final:
            return final
    return None


def get_lyric(sid, proxy=None, cookie=None):
    """获取 LRC 歌词文本"""
    try:
        data = _get(f"https://music.163.com/api/song/lyric?id={sid}&lv=1&kv=1&tv=-1",
                    proxy, cookie).json()
        return data.get("lrc", {}).get("lyric", "") or ""
    except Exception:
        return ""


def get_cover_url(sid, proxy=None, cookie=None):
    """获取单曲所属专辑封面 URL"""
    try:
        data = _get(f"https://music.163.com/api/song/detail/?id={sid}&ids=[{sid}]",
                    proxy, cookie).json()
        return ((data.get("songs") or [{}])[0].get("album") or {}).get("picUrl") or None
    except Exception:
        return None


def download_cover_bytes(url, proxy=None, cookie=None, timeout=10):
    """下载封面图片二进制；失败返回 None"""
    try:
        r = _get(url, proxy, cookie, timeout=timeout)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None
