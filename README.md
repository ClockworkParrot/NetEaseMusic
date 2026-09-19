# NetEase Music Client

基于 PyQt5 的第三方网易云音乐客户端。多源降级播放、本地曲库扫描、LRC 同步字幕、歌单导入导出、批量下载。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py

# 打包（三选一）
bash packaging/build_deb.sh 1.2.0     # Linux .deb
powershell packaging/build_exe.bat    # Windows .exe
bash packaging/build_mac.sh           # macOS .app
```

## 功能矩阵

| 模块 | 能力 |
|---|---|
| 搜索/发现 | URL 解析（playlist/album/song + 大小写不敏感） |
| 播放 | QMediaPlayer，多源降级（官方 API → outer link → hhtjim） |
| 下载 | 多线程、重试、并发钳制、封面嵌入、占位假文件校验 |
| 本地 | 递归扫描、WAV/MP3/FLAC/M4A、零帧残缺过滤 |
| LRC | 多时间戳、offset 钳制、二分定位、手动保存 |
| 设置 | JSON 持久化、损坏静默回退硬编码默认 |
| 代理 | HTTP / SOCKS5（匿名或带认证） |

## 目录

```
app/
  core/     api, lyrics, local_library, downloader, models, settings, playlist_io
  ui/       main_window, pages/{search,playlist,download,local,nowplaying,discover}, widgets/, dialogs/
tests/      selftest.py — 306 项断言
.github/    workflows/{ci,release}.yml
packaging/  build_deb.sh, build_exe.bat, build_mac.sh, icons
```

## CI

GitHub Actions 每次 push/PR 自动运行：

- `ci.yml`：3 平台 × 2 Python（macOS 只跑 3.10）跑 `tests/selftest.py`
- `release.yml`：push `v*.*.*` tag 时构建三平台安装包 → GitHub Release

## 版本

- `v1.0.0` — 首版
- `v1.0.1` — 修复多源降级
- `v1.0.2` — 修复 ID3v2.3 封面嵌入
- `v1.1.0` — 第三方客户端 UI 重写
- `v1.2.0` — 三轮回归全绿，306 项断言

详见 [OPTIMIZATION_REPORT.md](./OPTIMIZATION_REPORT.md)。

## 授权

MIT
