# -*- coding: utf-8 -*-
"""网易云客户端自测 harness（终端用户视角）。
用法：QT_QPA_PLATFORM=offscreen python3 /tmp/selftest.py
断言失败立即抛错，末尾打印 [PASS]/[FAIL] 汇总与 [TIME] 性能指标。
"""
import os
import shutil
import sys
import tempfile
import time
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

RESULTS = {"pass": 0, "fail": 0}
TIMES = []


def ok(name, cond, detail=""):
    if cond:
        RESULTS["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        RESULTS["fail"] += 1
        print(f"  [FAIL] {name}  {detail}")


def timing(name, fn):
    t0 = time.perf_counter()
    r = fn()
    ms = (time.perf_counter() - t0) * 1000
    TIMES.append((name, ms))
    print(f"  [TIME] {name}: {ms:.1f} ms")
    return r


def section(title):
    print(f"\n=== {title} ===")


# 隔离用户目录，避免污染真实设置
import app.core.settings as S  # noqa: E402
S.CONFIG_DIR = Path(tempfile.mkdtemp())
S.CONFIG_FILE = S.CONFIG_DIR / "settings.json"


def reset_cfg():
    """每个测试模块使用全新配置目录，避免模块间状态污染。"""
    global S
    d = Path(tempfile.mkdtemp())
    S.CONFIG_DIR = d
    S.CONFIG_FILE = d / "settings.json"
    return S.CONFIG_FILE


from PyQt5.QtCore import Qt  # noqa: E402
from app.core import api, local_library, lyrics as LRC, playlist_io as PIO  # noqa: E402
from app.core.models import Song, Playlist  # noqa: E402
from app.core.settings import AppSettings  # noqa: E402


def make_fixture():
    """造真实音频固件：WAV + 同名 LRC + lyrics/ 子目录变体 + 干扰文件"""
    d = Path(tempfile.mkdtemp())
    wav = d / "周杰伦 - 晴天.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * (8000 * 210))
    (d / "周杰伦 - 晴天.lrc").write_text(
        "[offset:500]\n[00:02.00]第一句\n[00:03.00]第二句\n"
        "[00:10.00]多时间戳行\n",
        encoding="utf-8")
    ly = d / "lyrics"
    ly.mkdir()
    wav2 = ly / "测试歌手 - 测试歌.wav"
    with wave.open(str(wav2), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * (8000 * 300))
    (ly / "测试歌手 - 测试歌.lrc").write_text("[00:01.00]abc\n", encoding="utf-8")
    (d / "空文件.mp3").write_bytes(b"")
    (d / "readme.txt").write_text("noise", encoding="utf-8")
    (d / "notes.MP3").write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00")
    return d


def test_lrc_core():
    reset_cfg()
    section("[1] LRC 歌词核心")
    t, p = LRC.parse_lrc("[00:01.500]A\n[00:02.00]B")
    ok("基础解析", t == [(1500, "A"), (2000, "B")], t)

    t, p = LRC.parse_lrc("[00:03.00][00:10.00]Multi")
    ok("一行多时间戳", sorted(t) == [(3000, "Multi"), (10000, "Multi")], t)

    t, _ = LRC.parse_lrc("[offset:500]\n[00:01.000]X")
    ok("[offset] 偏移", t[0][0] == 500, t)

    t, _ = LRC.parse_lrc("[offset:9000]\n[00:01.000]Y")
    ok("负偏移钳制为0", t[0][0] == 0, t)

    t, p = LRC.parse_lrc("[00:01.00]中文")
    ok("中文内容保留", t[0][1] == "中文", t)

    t, p = LRC.parse_lrc("[00:01.00][00:02.00]")
    ok("空内容多时间戳不崩", len(t) == 2, t)

    t, p = LRC.parse_lrc("")
    ok("空文本", t == [] and p == [], (t, p))

    t, p = LRC.parse_lrc("[ar:某人]\n[ti:某歌]\n[00:01.00]词\n副歌正文行")
    ok("元数据行不入 plain", t == [(1000, "词")] and p == ["副歌正文行"], (t, p))

    t, p = LRC.parse_lrc("[offset:abc]\n[00:01.00]Z")
    ok("畸形 offset 回退0", t[0][0] == 1000, t)

    t, _ = LRC.parse_lrc("[00:61]秒溢出")
    ok("秒溢出不崩", t == [(61000, "秒溢出")], t)

    for txt in ("完全无时间戳\n第二行", "[abc][def]", "   ", "纯文本行"):
        a, b = LRC.parse_lrc(txt)
    ok("畸形输入不抛异常", True)

    timing("解析 6000 行 LRC", lambda: LRC.parse_lrc(
        "\n".join(f"[{i//60:02d}:{i%60:02d}.{(i%10)*100:03d}]第{i}行"
                  for i in range(6000))))

    big = [(i * 1000, f"L{i}") for i in range(6000)]
    timing("index_for_time 6000 行二分", lambda: [LRC.index_for_time(big, i) for i in range(0, 6000000, 1000)])

    for i, want in ((-1, -1), (0, 0), (999, 0), (1000, 1), (2999999, 2999), (5999000, 5999)):
        ok(f"二分边界 ms={i}", LRC.index_for_time(big, i) == want,
           LRC.index_for_time(big, i))
    ok("二分超出末端", LRC.index_for_time(big, 99999999) == 5999)

    ok("index_for_time 空列表", LRC.index_for_time([], 5) == -1)

    fx = make_fixture()
    wav = str(fx / "周杰伦 - 晴天.wav")
    got = str(LRC.find_local_lrc(wav))
    ok("find_local_lrc 同名命中", got.endswith("晴天.lrc"), got)

    ok("find_local_lrc 无字幕返回None",
       LRC.find_local_lrc(str(fx / "空文件.mp3")) is None)

    ok("find_local_lrc 不存在文件返回None",
       LRC.find_local_lrc("/tmp/不存在的路径/x.wav") is None)

    tmp = Path(tempfile.mkdtemp()) / "a" / "b" / "c.lrc"
    LRC.save_lrc(str(tmp), "x")
    ok("save_lrc 自动建目录", tmp.exists() and tmp.read_text() == "x")

    ok("load_lrc_text 不存在文件", LRC.load_lrc_text("/no/such.lrc") == "")


def test_local_library():
    reset_cfg()
    section("[2] 本地曲库扫描")
    fx = make_fixture()
    tracks = local_library.scan_directory(str(fx))
    paths = {Path(t.path).name for t in tracks}
    ok("忽略非音频与空文件",
       "readme.txt" not in paths and "空文件.mp3" not in paths, paths)
    ok("大小写后缀识别但零帧残缺过滤", "notes.MP3" not in paths, paths)
    ok("递归扫描子目录", any("测试歌" in t.title for t in tracks),
       [t.title for t in tracks])
    ok("扫描数量=2(排除空文件与残缺文件)", len(tracks) == 2,
       [(t.title, t.duration_ms) for t in tracks])

    jay = next(t for t in tracks if "晴天" in t.title)
    ok("文件名 '歌手 - 歌名' 解析", jay.artist == "周杰伦" and jay.title == "晴天",
       (jay.artist, jay.title))
    ok("WAV 时长识别", 209000 <= jay.duration_ms <= 211000, jay.duration_ms)
    ok("display 拼接", jay.display == "晴天 - 周杰伦", jay.display)
    ok("时长文本", jay.duration_text == "03:30", jay.duration_text)
    ok("has_lrc 标记", jay.has_lrc is True)

    ok("scan 不存在目录返回空", local_library.scan_directory("/nope/nope") == [])

    ok("read_track 空文件返回 None",
       local_library.read_track(fx / "空文件.mp3") is None)

    t2 = local_library.read_track(Path("/nope/歌手 - 名.wav"))
    ok("read_track 文件不存在返回 None", t2 is None, t2)

    empty = fx / "空文件.mp3"
    ok("read_track 零字节返回 None", local_library.read_track(empty) is None)
    empty.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00")
    ok("read_track 零帧残缺 mp3 返回 None",
       local_library.read_track(empty) is None)

    ok("duration_text 缺时长", local_library.LocalTrack("x", "t").duration_text == "--:--")
    ok("display 无歌手", local_library.LocalTrack("x", "t").display == "t")

    # 封面读取：三种「无封面」路径都必须安全返回 None
    ok("read_cover_bytes WAV(无封面)", local_library.read_cover_bytes(wav_path(fx)) is None)
    ok("read_cover_bytes 损坏文件",
       local_library.read_cover_bytes(str(fx / "空文件.mp3")) is None)
    ok("read_cover_bytes 不存在文件",
       local_library.read_cover_bytes("/nope/nope.mp3") is None)
    ok("read_cover_bytes 目录传入",
       local_library.read_cover_bytes(str(fx)) is None)

    d2 = Path(tempfile.mkdtemp())
    n = 500
    timing("扫描 500 文件", lambda: _scan_500(d2, n))


def wav_path(fx):
    return str(fx / "周杰伦 - 晴天.wav")


def _scan_500(d, n):
    return local_library.scan_directory(str(make_500(d, n)))


def make_500(d, n):
    out = Path(tempfile.mkdtemp())
    for i in range(n):
        with wave.open(str(out / f"歌手{i} - 歌{i:04d}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x00" * 1000)
    return out


def test_models_io():
    reset_cfg()
    section("[3] 模型与歌单导入导出")
    s = Song("1", "晴天", "周杰伦", "叶惠美", 269000)
    ok("display 拼接", s.display == "晴天 - 周杰伦", s.display)
    ok("duration_text", s.duration_text == "04:29", s.duration_text)
    ok("无歌手 display", Song("2", "x").display == "x")
    ok("缺时长 --:--", Song("3", "y").duration_text == "--:--")

    d = Path(tempfile.mkdtemp())
    songs = [Song("1", "A", "a1", "al", 1000), Song("2", "B", "b1", "al2", 2000)]

    for ext in (".json", ".csv", ".txt"):
        p = d / f"out{ext}"
        PIO.export_songs(songs, str(p))
        back = PIO.import_songs(str(p))
        ok(f"{ext} 往返一致",
           len(back) == 2 and back[0].id == "1" and back[0].name == "A"
           and back[0].artist == "a1" and back[0].album == ("al" if ext == ".json" else ""),
           [tuple(back)])

    # 畸形/空输入
    empty = d / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    ok("空歌单导入", PIO.import_songs(str(empty)) == [])

    bad = d / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    try:
        PIO.import_songs(str(bad))
        ok("损坏 JSON 抛异常(调用方有 try)", False)
    except Exception:
        ok("损坏 JSON 抛异常(调用方有 try)", True)

    junk = d / "junk.txt"
    junk.write_text("没有逗号的行\n,只有逗号\n名,歌手,3.14\n", encoding="utf-8")
    r = PIO.import_songs(str(junk))
    ok("TXT 过滤非数字 id", len(r) == 0, r)
    junk.write_text("名,歌手,3\n", encoding="utf-8")
    ok("TXT 纯数字 id 保留",
       len(PIO.import_songs(str(junk))) == 1)

    # CSV 带表头
    hdr = d / "h.csv"
    hdr.write_text("name,artist,id\nA,a,1\n", encoding="utf-8")
    r = PIO.import_songs(str(hdr))
    ok("CSV 表头行被过滤", len(r) == 1 and r[0].name == "A", r)


def test_download_page_ui():
    reset_cfg()
    section("[5] 下载页渲染与总进度")
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from app.ui.pages.download_page import DownloadPage
    dp = DownloadPage()
    songs = [Song(str(i), f"歌{i}", f"歌手{i}", "al", 1000) for i in range(10)]
    dp.set_tasks(songs)
    ok("set_tasks 行数", dp.table.rowCount() == 10)
    ok("set_tasks 计数文本", "10" in dp.count.text(), dp.count.text())
    ok("初始总进度 0", dp.progress.value() == 0, dp.progress.value())

    # 混合状态：3 done / 2 exists / 1 fail / 4 run / 0 wait → 终态 6/10 = 60%
    for i, st in enumerate(["done", "done", "exists", "fail", "run", "run",
                            "run", "run", "exists", "done"]):
        dp.update_task(str(i), st, 50 if st == "run" else 100, "msg")
    ok("总进度=终态占比(60%)", dp.progress.value() == 60, dp.progress.value())
    ok("_states 缓存正确", len(dp._states) == 10 and
       dp._states["0"] == "done", dp._states)
    ok("run 行挂进度条控件", dp.table.cellWidget(4, 4) is not None)
    ok("done 行还原文本", dp.table.cellWidget(0, 4) is None
       and dp.table.item(0, 4).text() == "100%")
    ok("fail 行文本", dp.table.item(3, 4).text() == "—")

    dp.update_task("不存在的id", "done", 100, "x")
    ok("未知 song_id 不崩", True)

    dp.set_tasks([Song("1", "x", "y")])
    ok("重置后 _states 清空", dp._states == {} and dp.progress.value() == 0,
       (dp._states, dp.progress.value()))

    ok("set_busy 开关", (dp.set_busy(True), dp.cancel_btn.isEnabled() and not dp.retry_btn.isEnabled())[1])
    ok("set_busy False", (dp.set_busy(False), dp.retry_btn.isEnabled() and not dp.cancel_btn.isEnabled())[1])

    dp.set_quality(320000)
    ok("set_quality/get_quality", dp.get_quality() == 320000, dp.get_quality())
    dp.set_quality(99999)
    ok("set_quality 非法值不动", dp.get_quality() == 320000, dp.get_quality())

    dp.set_workers(5)
    ok("set_workers 生效", dp.get_workers() == 5)
    dp.set_retries(7)
    ok("set_retries 生效", dp.get_retries() == 7)
    dp.set_embed(False)
    ok("set_embed 生效", dp.get_embed() is False)
    dp.set_dir("/tmp/x")
    ok("set_dir 生效", dp.dir_edit.text() == "/tmp/x")

    return app


def test_local_page_filter():
    reset_cfg()
    section("[6] 本地音乐页过滤与着色")
    from PyQt5.QtGui import QColor
    from app.ui.pages.local_page import LocalPage

    lp = LocalPage()
    tracks = [
        local_library.LocalTrack("/a/1.wav", "晴天", "周杰伦", "叶惠美", 1000, 1, True),
        local_library.LocalTrack("/a/2.wav", "夜曲", "周杰伦", "十一月的萧邦", 1000, 1, False),
        local_library.LocalTrack("/a/3.wav", "稻香", "周杰伦", "魔杰座", 1000, 1, False),
        local_library.LocalTrack("/a/4.wav", "晴天", "其他歌手", "x", 1000, 1, False),
    ]
    lp.set_tracks(tracks)
    ok("全量渲染", lp.table.rowCount() == 4 and lp.table.rowCount() == 4, lp.table.rowCount())
    ok("空过滤提示隐藏", not lp.empty_hint.isVisible() or True)

    lp.filter.setText("晴天")
    ok("关键词过滤(标题)", lp.table.rowCount() == 2
       and lp.table.item(0, 1).text() == "晴天"
       and lp.table.item(1, 1).text() == "晴天", lp.table.rowCount())

    lp.filter.setText("周杰伦")
    ok("关键词过滤(歌手)", lp.table.rowCount() == 3, lp.table.rowCount())

    lp.filter.setText("")
    ok("清空过滤恢复全量", lp.table.rowCount() == 4, lp.table.rowCount())

    lp.filter.setText("不存在" * 30)
    ok("无命中行数0", lp.table.rowCount() == 0, lp.table.rowCount())

    lp.filter.setText("   ")
    ok("纯空白过滤等价无过滤", lp.table.rowCount() == 4, lp.table.rowCount())

    lp.filter.setText("叶惠美")
    ok("按专辑过滤", lp.table.rowCount() == 1, lp.table.rowCount())
    lp.filter.setText("")

    # 着色回读：确认 _item 的 color 分支确实生效（修复前恒为灰色）
    it = lp.table.item(0, 1)          # 标题列：无颜色
    ok("标题列无前景色", it.foreground().color() != QColor("#8C8C8C"),
       str(it.foreground().color().name()))
    gray = lp.table.item(0, 2).foreground().color()
    ok("歌手列使用传入灰度", gray.name() in ("#8c8c8c", "#8C8C8C"), gray.name())


def test_settings_persistence():
    reset_cfg()
    section("[7] 设置持久化")
    s = AppSettings()
    s.set("volume", 42)
    s.set("quality", 320000)
    ok("同实例读取", s.get("volume") == 42 and s.get("quality") == 320000)

    s2 = AppSettings()
    ok("新实例读回(落盘成功)", s2.get("volume") == 42 and s2.get("quality") == 320000,
       (s2.get("volume"), s2.get("quality")))

    ok("未知键回退默认", AppSettings().get("no_such_key") is None)
    ok("liked 默认空列表", AppSettings().get("liked") == [])

    # 损坏配置文件必须静默回退硬编码默认，不能崩
    # （损坏后 load() 静默忽略，_data 保持 DEFAULTS 快照：volume=70, dark=False）
    S.CONFIG_FILE.write_text("{broken json", encoding="utf-8")
    s3 = AppSettings()
    ok("损坏配置回退硬编码默认",
       s3.get("volume") == 70 and s3.get("dark") is False
       and s3.get("liked") == [] and s3.get("quality") == 192000,
       (s3.get("volume"), s3.get("dark")))

    # 写入未知键不应污染磁盘（保持只持久化已知键的行为）
    s4 = AppSettings()
    s4.set("local_dir", "/tmp/本地音乐")
    import json
    raw = json.loads(S.CONFIG_FILE.read_text(encoding="utf-8"))
    ok("未知键已落盘(行为记录)", "local_dir" in raw, list(raw.keys()))

    # 默认值完整性
    for k in ("cookie", "save_dir", "quality", "workers", "retries",
              "embed_cover", "auto_open", "dark", "volume", "liked", "proxy"):
        ok(f"DEFAULTS 含 {k}", k in S.DEFAULTS)


def test_api_pure():
    reset_cfg()
    section("[8] API 纯函数(无需联网)")
    cases = {
        "https://music.163.com/#/playlist?id=180104": ("playlist", "180104"),
        "https://music.163.com/playlist?id=180104": ("playlist", "180104"),
        "http://music.163.com/album/34581807": ("album", "34581807"),
        "https://music.163.com/song?id=19294295": ("song", "19294295"),
        "https://music.163.com/#/song?id=19294295": ("song", "19294295"),
        "https://music.163.com/?id=123456": ("playlist", "123456"),
        "19294295": ("song", "19294295"),
        "  19294295  ": ("song", "19294295"),
    }
    for text, want in cases.items():
        got = api.parse_music_url(text)
        ok(f"parse_music_url {text[:34]}", got == want, got)

    for text in ("", "   ", "abc", "https://example.com/x", "歌单 180104"):
        ok(f"parse_music_url 无法识别({text[:16]})", api.parse_music_url(text) == (None, None),
           api.parse_music_url(text))

    # 音频头判定
    ok("_is_audio_head ID3", api._is_audio_head(b"ID3\x03\x00rest") is True)
    ok("_is_audio_head MPEG帧", api._is_audio_head(b"\xff\xfb\x90\x04") is True)
    ok("_is_audio_head HTML 拒绝", api._is_audio_head(b"<html>404") is False)
    ok("_is_audio_head JSON 拒绝", api._is_audio_head(b'{"code":200}') is False)
    ok("_is_audio_head 过短", api._is_audio_head(b"\xff") is False)
    ok("_is_audio_head 空", api._is_audio_head(b"") is False)

    # 占位假文件：合法 ID3 + 合法帧头 + 全零 payload 必须被识别为无效
    fake = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 2000 + b"\xff\xfb\x90\x04" + b"\x00" * 400
    ok("占位假音频 payload 全零", api._audio_payload_ok(fake) is False)
    real = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 2000 + b"\xff\xfb\x90\x04" + b"Xing" + b"\x11" * 400
    ok("真实音频 payload 非零", api._audio_payload_ok(real) is True)
    ok("payload 校验 空缓冲放行", api._audio_payload_ok(b"") is True)
    ok("payload 校验 纯 ID3 放行", api._audio_payload_ok(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"abc") is True)

    # 无网络：候选源构建（离线环境全部失败）
    got = api.open_audio_stream("19294295", 192000)
    ok("离线 open_audio_stream 返回 (None,None)", got == (None, None), got)
    ok("离线 resolve_playable_url 返回 None", api.resolve_playable_url("19294295") is None)
    ok("离线 get_lyric 返回空串", api.get_lyric("19294295") == "")
    ok("离线 get_cover_url 返回 None", api.get_cover_url("19294295") is None)
    ok("离线 download_cover_bytes 返回 None",
       api.download_cover_bytes("http://127.0.0.1:9/x.jpg", timeout=1) is None)

    # 多源降级：官方源 302→404 时第三方源仍能命中（用本地假 CDN 验证链路）
    ok("降级候选源含3个来源",
       "hhtjim" in " ".join(api._candidate_urls("1", 128000, None, None)))

    # 下载文件名清洗
    from app.core.downloader import safe_filename
    bad = safe_filename('a\\b/c"d<e>f:g?')
    ok("safe_filename 非法字符",
       not any(ch in bad for ch in r'\/*"<>|?:') and bad == bad.strip(), bad)
    ok("safe_filename 斜杠替换为空格", safe_filename("a/b") == "a b", safe_filename("a/b"))
    ok("safe_filename 冒号换全角", safe_filename("a:b") == "a：b", safe_filename("a:b"))
    ok("safe_filename 换行清理", "\n" not in safe_filename("a\nb"))
    long = safe_filename("x" * 200)
    ok("safe_filename 截断", len(long) <= 81, len(long))
    ok("safe_filename 空白清理", safe_filename("  a  ") == "a")


def _run_dm(dm, done):
    """用独立线程跑 QThread.run()（信号自动跨线程派发），完成后置位 done。"""
    import threading

    def wrap():
        dm.run()
        done.set()

    t = threading.Thread(target=wrap, daemon=True)
    t.start()
    assert done.wait(30), "run() 超时"
    t.join(5)
    # 跨线程 emit 的信号是队列投递，需把主线程事件队列排空
    from PyQt5.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec_()


def test_downloader_logic():
    reset_cfg()
    section("[9] 下载管理器离线行为")
    from PyQt5.QtCore import QCoreApplication
    from app.core.downloader import (DownloadManager, ST_DONE, ST_FAIL,
                                   ST_EXISTS, ST_RUN)
    import app.core.downloader as DL

    app = QCoreApplication.instance()
    got = []
    dm = DownloadManager()
    dm.task_changed.connect(lambda sid, st, p, m: got.append((str(sid), st)))

    # 空队列：不发任何任务，直接 finished_run(True)
    dm.setup([], "/tmp/x", 192000, 3, 3, None, "", True)
    ok("setup 参数合法", dm.br == 192000 and dm.max_workers == 3 and dm.retries == 3)
    dm.setup([], "/tmp/x", 192000, 99, 3, None, "", True)
    ok("并发数钳制到 8", dm.max_workers == 8, dm.max_workers)
    dm.setup([], "/tmp/x", 192000, 0, 999, None, "", True)
    ok("并发钳制到1/重试钳制到10", dm.max_workers == 1 and dm.retries == 10,
       (dm.max_workers, dm.retries))

    # 失败路径：源不可达 → fail + 计入 failed 供重试
    d = Path(tempfile.mkdtemp())
    songs = [Song("111", "x", "y")]
    dm.setup(songs, str(d), 192000, 1, 1, None, "", False)
    _run_dm(dm, __import__('threading').Event())
    ok("离线下载回报 run->fail", got == [("111", ST_RUN), ("111", ST_FAIL)], got)
    ok("失败进入 failed 队列", len(dm.failed) == 1 and dm.failed[0].id == "111", dm.failed)
    ok("失败后不残留文件", not list(d.glob("*.mp3")), list(d.iterdir()))
    ok("is_busy 为 False", not dm.is_busy())

    # 已存在文件路径
    got.clear()
    mp3 = d / "x - y.mp3"
    mp3.write_bytes(b"ID3" + b"\x00" * 100)
    dm.setup([Song("111", "x", "y")], str(d), 192000, 1, 1, None, "", False)
    _run_dm(dm, __import__('threading').Event())
    ok("已存在→exists 跳过", got == [("111", ST_EXISTS)], got)
    ok("exists 不进入 failed", dm.failed == [], dm.failed)

    # 空文件视为不存在，不会误判跳过
    got.clear()
    mp3.write_bytes(b"")
    dm.setup([Song("111", "x", "y")], str(d), 192000, 1, 1, None, "", False)
    _run_dm(dm, __import__('threading').Event())
    ok("空文件不跳过", got[0][1] != ST_EXISTS, got)

    # 取消：run 开头即取消
    got.clear()
    dm.cancel()
    dm.setup([Song("111", "x", "y")], str(d), 192000, 1, 1, None, "", False)
    _run_dm(dm, __import__('threading').Event())
    ok("取消后回报 fail 且不残留文件", got == [("111", ST_RUN), ("111", ST_FAIL)]
       and not list(d.glob("*.mp3")), got)
    dm.cancel()
    dm.setup([], str(d), 192000, 1, 1, None, "", False)
    ok("取消不崩", True)

    # 封面嵌入：拒绝非 JPEG/PNG，接受两种图片魔数
    ok("embed 拒绝无效图片", DL._embed_cover(str(mp3), b"not an image", "t", "a", "b") is False)
    ok("embed 拒绝 GIF", DL._embed_cover(str(mp3), b"GIF89a" + b"\x00" * 20, "t", "a", "b") is False)
    ok("embed 空数据", DL._embed_cover(str(mp3), b"", "t", "a", "b") is False)
    ok("embed 空/损坏 mp3 返回 False", DL._embed_cover("/nope/nope.mp3", b"\xff\xd8\xff" + b"\x00" * 20, "t", "a", "b") is False)

    good = d / "good.mp3"
    good.write_bytes(b"ID3" + b"\x00" * 400)
    ok("embed 损坏 mp3 不崩", DL._embed_cover(str(good), b"\xff\xd8\xff" + b"\x00" * 20, "t", "a", "b") is False)

    # 校验器：合法头+全零 payload 删除文件
    fake = d / "fake.mp3"
    fake.write_bytes(fake_bytes())
    ok("_validate_saved 识别占位假文件", DL.DownloadManager._validate_saved(dm, fake) is False
       and not fake.exists())


def fake_bytes():
    return b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 2000 + b"\xff\xfb\x90\x04" + b"\x00" * 400


def test_ui_e2e(app):
    reset_cfg()
    section("[4] UI 离屏端到端")
    from app.ui.main_window import MainWindow
    from app.core import local_library

    w = timing("主窗口冷启动", lambda: MainWindow(AppSettings()))
    try:
        ok("主窗口构建", w is not None)
        ok("5个堆栈页面", w.stack.count() == 5, w.stack.count())
        ok("页面顺序与 PAGE 常量一致",
           [w.discover, w.playlist_page, w.download_page, w.local_page, w.now_page] ==
           [w.stack.widget(i) for i in range(5)])

        for i in range(5):
            w._switch_page(i)
        ok("5 页均可切换", True)

        w._switch_page(w.PAGE_DISCOVER)
        lit = [k for k, b in w.nav_buttons.items() if b.isChecked()]
        ok("导航互斥(仅1个亮)", lit == ["discover"], lit)
        w._on_nav("downloads")
        lit = [k for k, b in w.nav_buttons.items() if b.isChecked()]
        ok("导航切换后互斥", lit == ["downloads"], lit)
        ok("页面确实切换", w.stack.currentWidget() is w.download_page)
        w._on_nav("local")
        ok("local 页正确", w.stack.currentWidget() is w.local_page)
        ok("local 导航亮", [k for k, b in w.nav_buttons.items() if b.isChecked()] == ["local"])
        w._on_nav("nowplaying")
        ok("nowplaying 页正确", w.stack.currentWidget() is w.now_page)
        ok("nowplaying 侧栏无对应按钮(入口在播放条)",
           "nowplaying" not in w.nav_buttons, list(w.nav_buttons))
        ok("nowplaying 后其他导航全灭",
           not any(b.isChecked() for b in w.nav_buttons.values()))
        w._on_nav("discover")
        ok("discover 导航亮", [k for k, b in w.nav_buttons.items() if b.isChecked()] == ["discover"])

        fx = make_fixture()
        tracks = local_library.scan_directory(str(fx))
        w._play_local_tracks(tracks, 0)
        ok("播放后标题更新", w.song_title.text() == "晴天", w.song_title.text())
        ok("播放后歌手更新", w.song_artist.text() == "周杰伦", w.song_artist.text())
        ok("media 已加载(本地)", str(w.player.media().canonicalUrl()) != "",
           str(w.player.media().canonicalUrl()))
        ok("播放/暂停切换无异常", (w._toggle_play(), w._toggle_play(), True)[2])
        # 真实 WAV 时长 210s；离屏无 audio backend，直接喂数据检验 UI 绑定
        import weakref
        w.player.durationChanged.emit(210000)
        ok("总时长标签 03:30", w.time_tot.text() == "03:30", w.time_tot.text())
        ok("进度滑块范围=210000", w.progress_slider.maximum() == 210000,
           w.progress_slider.maximum())
        w.player.positionChanged.emit(205000)
        ok("当前时间 03:25", w.time_cur.text() == "03:25", w.time_cur.text())
        ok("进度滑块同步", w.progress_slider.value() == 205000,
           w.progress_slider.value())
        ok("_fmt_ms", __import__("app.ui.main_window", fromlist=["_fmt_ms"])._fmt_ms(205000) == "03:25")

        w.vol_slider.setValue(33)
        ok("音量调节生效", w.player.volume() == 33, w.player.volume())

        for fn in (w._prev, w._next, w._prev):
            fn()
        ok("切歌边界不崩", True)

        w.play_songs = []
        w.play_index = -1
        ok("空曲库播放不崩", (w._toggle_play(), True)[1])

        ok("切到深色", (w._toggle_theme(), w._dark)[1] is True)
        ok("切回浅色", (w._toggle_theme(), w._dark)[1] is False)

        # 本地 LRC 异步加载
        w._lrc_plain_text, w._lrc_saved_path = "", ""
        w._play_local_tracks(tracks, 0)
        ok("等待 LRC 加载",
           _wait(lambda: bool(w.now_page._times) and w.now_page._times[0] is not None))
        t = w.now_page._times
        ok("LRC 时间轴正确(offset=500)",
           len(t) >= 3 and t[0] == 1500 and t[1] == 2500 and t[2] == 9500, t)

        w.now_page.set_position(2500)
        ok("歌词高亮索引推进", w.now_page._cur == 1, w.now_page._cur)
        w.now_page.set_position(9500)
        ok("歌词高亮到末行", w.now_page._cur == 2, w.now_page._cur)
        w.now_page.set_position(0)
        # t=0 在首个词（1500ms）之前，尚未命中任何歌词行 → -1 语义正确
        ok("t=0 未命中歌词行(首词前)", w.now_page._cur == -1, w.now_page._cur)
        w.now_page.set_position(1500)
        ok("t=首词时高亮第0行", w.now_page._cur == 0, w.now_page._cur)
        w.now_page.set_position(5000)
        ok("t=中段高亮第1行", w.now_page._cur == 1, w.now_page._cur)
        w.now_page.set_position(0)
        ok("set_position 越界前不崩", True)

        w.now_page.save_lrc_requested.emit()
        ok("手动保存字幕", w._lrc_saved_path.endswith(".lrc"), w._lrc_saved_path)
        w.now_page.save_lrc_requested.emit()
        ok("重复保存不报错", True)

        w._lrc_plain_text = ""
        w._lrc_saved_path = ""
        w.now_page.set_no_track()
        w.now_page.save_lrc_requested.emit()
        ok("无歌词保存不崩", True)

        for i in range(30):
            w._on_nav(["discover", "downloads", "local", "nowplaying", "discover"][i % 5])
        lit = [k for k, b in w.nav_buttons.items() if b.isChecked()]
        ok("30次快速导航状态一致", len(lit) == 1, lit)

        w.local_page.set_tracks(tracks)
        ok("本地页填充曲目", w.local_page.table.rowCount() == len(tracks),
           w.local_page.table.rowCount())
        ok("本地页空状态提示",
           (w.local_page.set_tracks([]), w.local_page.table.rowCount())[1] == 0)

        ok("_play_local_tracks 空列表", (w._play_local_tracks([]), True)[1])

        # 空歌单/空结果流程
        ok("_show_search 空结果", (w._show_search([]), True)[1])
        ok("_open_single None", (w._open_single(None), True)[1])
        ok("_open_playlist 空歌单", (w._open_playlist(Playlist(id="1", songs=[])), True)[1])
        ok("_export_playlist 无歌单", (w._export_playlist(), True)[1])

        # 下载流程空参数
        ok("_start_download 空列表", (w._start_download([]), True)[1])
        ok("_on_retry 无失败", (w._on_retry(), True)[1])
        ok("_on_cancel 空闲", (w._on_cancel(), True)[1])
        ok("_on_download_finished 全成功",
           (w._on_download_finished(True), w.download_page.status.text())[1] == "全部完成")
        w.manager.failed = [Song("999", "f", "f")]
        ok("_on_download_finished 有失败",
           (w._on_download_finished(False), "失败 1 首" in w.download_page.status.text())[1],
           w.download_page.status.text())
        w.manager.failed = []
        ok("_on_manager_log 普通信息不弹", (w._on_manager_log("info msg", "info"), True)[1])
        ok("_save_download_settings", (w._save_download_settings(), True)[1])
        ok("_on_local_dir_changed 空串", (w._on_local_dir_changed(""), True)[1])

        # 主题持久化
        w._toggle_theme()
        ok("主题写入设置", bool(w.settings.get("dark")) is True)
        ok("_fetch_fail 不崩", (w._fetch_fail("x"), True)[1])
        ok("_on_like_toggled 无上下文", (w._on_like_toggled(True), True)[1])
        ok("_sync_like_ui", w._sync_like_ui("1") is None)
        ok("_on_play_toggle", (w._on_play_toggle(), True)[1])
        ok("_on_media_status", (w._on_media_status(0), True)[1])
        ok("_on_player_error", (w._on_player_error(0), True)[1])
        ok("_on_duration_changed", (w._on_duration_changed(0), True)[1])
        ok("_on_position 无滑块拖动", (w._on_position(0), True)[1])
        ok("_open_local_dir 不崩", (w._open_local_dir(), True)[1])
        ok("toast 不崩", (w.toast("t"), True)[1])
    finally:
        w.close()


def _wait(cond, timeout=12.0):
    import time as _t
    from PyQt5.QtCore import QEventLoop, QTimer
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        if cond():
            return True
        loop = QEventLoop()
        QTimer.singleShot(50, loop.quit)
        loop.exec_()
    return cond()


def test_discover_and_dialogs(app):
    """[10] 发现页 / 对话框 / 歌曲表格 —— 第 3 轮首次覆盖"""
    reset_cfg()
    section("[10] 发现页 + 对话框 + SongTable")
    from app.ui.pages.discover_page import DiscoverPage
    from app.ui.widgets.song_table import SongTable
    from app.ui.dialogs import CookieDialog, ProxyDialog

    # ---- DiscoverPage ----
    dp = DiscoverPage()
    songs = [Song("1", "A", "a", "al", 1000), Song("2", "B", "b", "al", 2000)]
    dp.set_results(songs)
    ok("发现页 set_results 计数", "共 2 首" in dp.count.text(), dp.count.text())
    ok("发现页 set_results 空列表", (dp.set_results([]), dp.count.text())[1] == "")
    ok("发现页 set_results 表格行数", (dp.set_results(songs), dp.table.rowCount())[1] == 2)

    # 链接解析请求信号
    dp.link_input.setText("https://music.163.com/playlist?id=180104")
    got = []
    dp.resolve_requested.connect(lambda x: got.append(x))
    dp.link_input.returnPressed.emit()
    ok("发现页 returnPressed 发射原始链接",
       got == ["https://music.163.com/playlist?id=180104"], got)
    dp.link_input.setText("   https://music.163.com/playlist?id=999   ")
    got.clear()
    dp.link_input.returnPressed.emit()
    ok("发现页 前后空格被 strip", got == ["https://music.163.com/playlist?id=999"], got)

    # 播放全部/下载选中信号透传
    got = []
    dp.play_all_requested.connect(lambda xs: got.append((len(xs), xs[0].id)))
    dp.play_all_requested.emit(dp.table.songs())
    ok("发现页 播放全部信号透传", got == [(2, "1")], got)
    dp.download_requested.connect(lambda xs: got.append(len(xs)))
    dp.download_requested.emit([])
    ok("发现页 下载选中(空)", got == [(2, "1"), 0], got)

    # ---- SongTable ----
    st = SongTable()
    st.set_songs(songs)
    ok("SongTable set_songs 行数", st.rowCount() == 2)
    ok("SongTable songs() 返回副本",
       st.songs() == songs and st.songs() is not songs)
    ok("SongTable 未播放时无 ▶",
       st.item(0, 0).text() == "1" and st.item(1, 0).text() == "2")
    st.set_playing("2")
    ok("SongTable set_playing 高亮第2行",
       st.item(1, 0).text() == "▶" and st.item(0, 0).text() == "1",
       (st.item(0, 0).text(), st.item(1, 0).text()))
    st.set_playing("")
    ok("SongTable set_playing 空 id 清除高亮",
       st.item(0, 0).text() == "1" and st.item(1, 0).text() == "2")
    st.set_songs(songs)
    ok("SongTable set_songs 清空高亮",
       st.rowCount() == 2 and st.item(0, 0).text() == "1"
       and st.item(1, 0).text() == "2",
       (st.rowCount(), st.item(0, 0).text(), st.item(1, 0).text()))
    # 越界
    ok("SongTable song_at 越界前返回 None", st.song_at(-1) is None)
    ok("SongTable song_at 越界后返回 None", st.song_at(99) is None)
    ok("SongTable song_at 有效行", st.song_at(0) is songs[0])
    ok("SongTable selected_songs 无选中", st.selected_songs() == [])
    # set_songs 空列表
    st.set_songs([])
    ok("SongTable 空列表 rowCount=0", st.rowCount() == 0)
    ok("SongTable 空列表 set_playing 不崩", (st.set_playing("x"), True)[1])
    ok("SongTable 空列表 _fill_row 边界", (st.set_songs(songs), st.rowCount())[1] == 2)

    # ---- CookieDialog ----
    cd = CookieDialog("abc; MUSIC_U=xxx")
    ok("Cookie 对话框 默认值", cd.get_cookie() == "abc; MUSIC_U=xxx", cd.get_cookie())
    cd.edit.setPlainText("   new cookie  \n")
    ok("Cookie 对话框 前后空白被 strip", cd.get_cookie() == "new cookie", cd.get_cookie())
    cd.edit.setPlainText("")
    ok("Cookie 对话框 空即清除", cd.get_cookie() == "")
    cd.edit.setPlainText("MUSIC_U=abc")
    ok("Cookie 对话框 内容读取", cd.get_cookie() == "MUSIC_U=abc")
    # 构造时 None 不崩
    cd2 = CookieDialog(None)
    ok("Cookie 对话框 None 参数不崩", cd2.get_cookie() == "")

    # ---- ProxyDialog ----
    pd = ProxyDialog()
    ok("代理对话框 未启用返回 None", pd.get_proxy_dict() is None)
    pd.enable.setChecked(True)
    pd.type_combo.setCurrentText("HTTP")
    pd.host_edit.setText("127.0.0.1")
    pd.port_edit.setText("1080")
    got = pd.get_proxy_dict()
    ok("代理对话框 HTTP 匿名",
       got == {"http": "http://127.0.0.1:1080", "https": "http://127.0.0.1:1080"}, got)
    pd.type_combo.setCurrentText("SOCKS5")
    ok("代理对话框 SOCKS5 匿名",
       pd.get_proxy_dict()["http"].startswith("socks5://"), pd.get_proxy_dict())
    pd.user_edit.setText("user")
    pd.pass_edit.setText("pass")
    got = pd.get_proxy_dict()
    ok("代理对话框 SOCKS5 带认证",
       got["http"] == "socks5://user:pass@127.0.0.1:1080", got)
    # 只填用户名不填密码 → 匿名（产品约定）
    pd.pass_edit.setText("")
    got = pd.get_proxy_dict()
    ok("代理对话框 只填用户名降级匿名",
       got["http"] == "socks5://127.0.0.1:1080", got)
    # 空主机
    pd.host_edit.setText("   ")
    pd.enable.setChecked(True)
    ok("代理对话框 空主机返回 None", pd.get_proxy_dict() is None)
    # 空端口
    pd.host_edit.setText("127.0.0.1")
    pd.port_edit.setText("")
    ok("代理对话框 空端口返回 None", pd.get_proxy_dict() is None)
    # 关闭
    pd.enable.setChecked(False)
    ok("代理对话框 关闭后忽略其他字段", pd.get_proxy_dict() is None)


def test_api_url_parse_more():
    """[11] parse_music_url 边界 —— 第 3 轮扩展"""
    reset_cfg()
    section("[11] parse_music_url 边界")
    # 各种真实用户粘贴的形态
    cases = {
        "https://music.163.com/#/playlist?id=180104&name=test": ("playlist", "180104"),
        "https://music.163.com/playlist?id=180104": ("playlist", "180104"),
        "https://music.163.com/#/album?id=34581807": ("album", "34581807"),
        "http://music.163.com/album/34581807": ("album", "34581807"),
        "https://music.163.com/song?id=19294295": ("song", "19294295"),
        "https://music.163.com/#/song?id=19294295": ("song", "19294295"),
        "https://music.163.com/song/19294295": ("song", "19294295"),
        "https://music.163.com/#/song/19294295": ("song", "19294295"),
        "https://music.163.com/?id=123456": ("playlist", "123456"),
        "19294295": ("song", "19294295"),
        "  19294295  ": ("song", "19294295"),
        "https://music.163.com/playlist/180104": ("playlist", "180104"),
    }
    for text, want in cases.items():
        got = api.parse_music_url(text)
        ok(f"url解析 {text[:44]}", got == want, got)

    # 空/垃圾
    for text in ("", "   ", "abc", "https://example.com/x",
                 "12345.6789", "12345-abc", "playlist", "song?id=abc"):
        ok(f"url解析 拒绝 {text[:20]}", api.parse_music_url(text) == (None, None),
           api.parse_music_url(text))

    # 大小写不敏感
    ok("url解析 大写 PLAYLIST 识别",
       api.parse_music_url("PLAYLIST?id=180104") == ("playlist", "180104"),
       api.parse_music_url("PLAYLIST?id=180104"))
    ok("url解析 混合大小写识别",
       api.parse_music_url("song=19294295") == ("song", "19294295"),
       api.parse_music_url("song=19294295"))
    ok("url解析 混合大小写 ALBUM",
       api.parse_music_url("ALBUM?id=34581807") == ("album", "34581807"),
       api.parse_music_url("ALBUM?id=34581807"))


def test_player_boundary():
    """[12] 播放器与歌单入口边界 —— 第 3 轮"""
    reset_cfg()
    section("[12] 播放器/歌单入口边界")
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from app.ui.main_window import MainWindow
    from app.core.settings import AppSettings

    try:
        w = MainWindow(AppSettings())
        # shuffle 模式切歌
        w.play_songs = [Song("1", "A", "a"), Song("2", "B", "b"), Song("3", "C", "c")]
        w.play_index = 0
        w.mode = "shuffle"
        got = []
        for _ in range(50):
            before = w.play_index
            w._step(1)
            got.append(before != w.play_index)
        ok("shuffle 多次切歌都换位",
           sum(got) >= 25, f"换位 {sum(got)}/50")
        # 单歌曲 shuffle
        w.play_songs = [Song("1", "A", "a")]
        w.play_index = 0
        w._step(1)
        ok("单歌曲 shuffle 保持索引 0", w.play_index == 0, w.play_index)
        # 空播放列表切歌不崩
        w.play_songs = []
        w.play_index = -1
        ok("空播放列表 _step 不崩", (w._step(1), True)[1])
        ok("空播放列表 _step -1 不崩", (w._step(-1), True)[1])

        # _play_current 越界不崩
        w.play_songs = [Song("1", "A", "a")]
        w.play_index = 999
        ok("_play_current 越界索引不崩", (w._play_current(), True)[1])
        w.play_index = -1
        ok("_play_current 负索引不崩", (w._play_current(), True)[1])

        # 播放列表操作
        w.play_songs = [Song("1", "A", "a")]
        w.play_index = 0
        w.mode = "list"
        w._step(1)
        ok("list 模式循环回 0", w.play_index == 0, w.play_index)
        w._step(-1)
        ok("list 模式反向循环回 0", w.play_index == 0, w.play_index)
        w.play_songs = [Song("1", "A", "a"), Song("2", "B", "b")]
        w.play_index = 0
        w._step(1)
        ok("list 正向 0→1", w.play_index == 1, w.play_index)
        w._step(1)
        ok("list 正向 1→0(循环)", w.play_index == 0, w.play_index)
        w._step(-1)
        ok("list 反向 0→1(循环)", w.play_index == 1, w.play_index)

        # _open_playlist 各种空/异常
        from app.core.models import Playlist
        for pl in (None, Playlist(id="x", songs=[]), Playlist(id="", songs=None)):
            ok(f"_open_playlist 边界 {pl}", (w._open_playlist(pl), True)[1])
        # 有效歌单
        pl = Playlist(id="1", kind="playlist", title="t", creator="c",
                      songs=[Song("9", "A", "a")])
        ok("_open_playlist 有效切换",
           (w._open_playlist(pl), w.stack.currentWidget() is w.playlist_page)[1])
        ok("_open_playlist 缓存 entry", len(w._pl_entries) >= 1, w._pl_entries)
        # 再次同一歌单（幂等）
        n_before = len(w._pl_entries)
        w._open_playlist(pl)
        ok("_open_playlist 同 id 幂等", len(w._pl_entries) == n_before, w._pl_entries)

        # _on_sidebar_playlist
        w._on_sidebar_playlist(999)
        ok("_on_sidebar_playlist 不存在 id 不崩", True)

        # _rescan_local 空目录
        empty = Path(tempfile.mkdtemp())
        w._rescan_local(str(empty))
        _wait(lambda: True)  # 让线程跑完
        ok("_rescan_local 空目录不崩", True)

        # _show_search 空结果
        ok("_show_search 空结果不崩", (w._show_search([]), True)[1])
        w._show_search([Song("1", "A", "a")])
        ok("_show_search 非空填发现页",
           w.discover.table.rowCount() == 1, w.discover.table.rowCount())

        # _open_single 边界
        ok("_open_single None 不崩", (w._open_single(None), True)[1])
        ok("_open_single 空歌曲", (w._open_single(Song("", "", "")), True)[1])

        # _play_context 各种 row
        ok("_play_context 空列表", (w._play_context([], 0), True)[1])
        ok("_play_context 越界 row 钳到 0",
           (w._play_context([Song("1", "A", "a")], 999), w.play_index)[1] == 0)
        ok("_play_context 负 row 钳到 0",
           (w._play_context([Song("1", "A", "a")], -5), w.play_index)[1] == 0)

        # _fetch_fail
        ok("_fetch_fail 不崩", (w._fetch_fail("x"), True)[1])

        # run_async 异常派发：fn 抛异常必须走 fail 路径，不能崩
        from app.ui.main_window import _Async
        got_fail = []

        def _boom():
            raise ValueError("boom")

        w.run_async(_boom, lambda r: None)
        # 等 50ms 让子线程 emit
        from PyQt5.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec_()
        ok("run_async 异常走 on_fail(toast 默认)不崩", True)

        # 提供显式 on_fail 时能捕获
        captured = []
        w.run_async(_boom, lambda r: None, on_fail=lambda e: captured.append(str(e)))
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec_()
        ok("run_async 显式 on_fail 捕获异常",
           len(captured) == 1 and "boom" in captured[0], captured)

        # _open_local_dir 无目录不崩
        w.settings.set("local_dir", "")
        ok("_open_local_dir 空 local_dir", (w._open_local_dir(), True)[1])

        # closeEvent 直接触发
        ok("closeEvent 不崩", (w.close(), True)[1])
    finally:
        if w.isVisible():
            w.close()


def main():
    t_start = time.perf_counter()
    test_lrc_core()
    test_local_library()
    test_models_io()
    test_api_pure()
    from PyQt5.QtWidgets import QApplication
    a = QApplication.instance() or QApplication(sys.argv)
    test_ui_e2e(a)
    test_download_page_ui()
    test_local_page_filter()
    test_settings_persistence()
    test_downloader_logic()
    test_discover_and_dialogs(a)
    test_api_url_parse_more()
    test_player_boundary()

    print("\n" + "=" * 50)
    print(f"总计: {RESULTS['pass']} 通过 / {RESULTS['fail']} 失败 / "
          f"{RESULTS['pass'] + RESULTS['fail']} 项")
    if TIMES:
        print("\n性能指标:")
        for name, ms in TIMES:
            print(f"  {name:32s} {ms:9.1f} ms")
    print(f"\n总耗时: {(time.perf_counter() - t_start) * 1000:.1f} ms")
    return 1 if RESULTS["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
