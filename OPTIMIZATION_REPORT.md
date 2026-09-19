# 三轮回归优化报告

## 摘要

对 NetEaseMusic（PyQt5 网易云第三方客户端）执行 **3 轮"测试 → 优化 → 验证"完整循环**，harness 从 57 项扩至 306 项，累计修复 11 处缺陷，性能指标显著改善，最终 **306/306 全绿** 并打包发布 v1.2.0。

## 三轮通过率演进

| 轮次 | 断言数 | 通过 | Commit | 耗时 |
|---|---:|---:|---|---|
| Round 1 | 57 | 57/57 | `b4d790a` | ~2 s |
| Round 2 | 219 | 219/219 | `8811764` | ~9 s |
| Round 3 | 306 | 306/306 | `13a50a3` | ~12 s |

## 测试 harness 结构（12 模块）

```
[1] LRC 歌词核心          解析 / offset / 多时间戳 / 二分 / 保存 / find_local_lrc
[2] 本地曲库扫描          递归 / 残缺过滤 / 封面读取 / 500 文件扫描性能
[3] 模型与歌单导入导出     JSON/CSV/TXT 往返、表头、损坏文件
[4] UI 离屏端到端         主窗口 / 导航 / 播放 / LRC / 主题 / 下载 / 歌单
[5] 下载页渲染            set_tasks / update_task / 总进度 / 边界
[6] 本地页过滤与着色      关键词 / 专辑 / 灰度
[7] 设置持久化            落盘 / 未知键 / 损坏回退 / DEFAULTS 完整性
[8] API 纯函数            parse_music_url / _is_audio_head / _audio_payload_ok / 下载文件名
[9] 下载管理器离线行为    并发钳制 / 失败重试 / 已存在 / 取消 / 封面嵌入
[10] 发现页 + 对话框      DiscoverPage / SongTable / CookieDialog / ProxyDialog
[11] parse_music_url 边界 大小写 / 混合分隔符 / 纯数字 / 拒绝垃圾
[12] 播放器边界           shuffle/list 模式 / run_async 异常 / closeEvent
```

## 三轮累计修复的 11 处缺陷

### Round 2（6 处 · commit `8811764`）

| # | 缺陷 | 修复 | 文件 |
|---|---|---|---|
| 1 | Sidebar 选中色对比度过低（`#FFFFFF`） | 改为品牌色 `#FC5E6F` | `sidebar.py` |
| 2 | `_on_sidebar_clicked` 未刷新当前页 | 补 `show()` + `raise_()` | `main_window.py` |
| 3 | 深色模式白色残留 `#F8F8F8` | 用调色板中性色 | `main_window.py` |
| 4 | LRC 未命中行 `_cur` 未重置 | 命中失败时 `_cur = -1` | `pages/nowplaying_page.py` |
| 5 | `parse_playlist` 未处理大写 `?id=` | 加 `.lower()` | `api.py` |
| 6 | LocalPage 歌手列缺 `_GRAY` 灰度 | `_item(t.artist, _GRAY)` | `pages/local_page.py` |

### Round 3（5 处 · commit `13a50a3`）

| # | 缺陷 | 修复 | 文件 |
|---|---|---|---|
| 7 | `parse_music_url` 大小写敏感 | 归一化 `.lower()` | `api.py` |
| 8 | `_open_local_dir` 崩溃（QDesktopServices 离屏 core dump） | try/except + toast 降级 | `main_window.py` |
| 9 | `AppSettings.load()` 损坏 JSON 语义 | 静默回退硬编码 DEFAULTS | `settings.py` |
| 10 | `_show_search` 空结果分支元组语法 | 独立断言 + 返回 | `main_window.py` |
| 11 | `SongTable.set_songs` 未清 `_hi` 高亮 | 重置 `_hi = None` | `widgets/song_table.py` |

## 性能指标演进

| 项 | Round 1 | Round 3 | 变化 |
|---|---:|---:|---|
| LRC 解析 6000 行 | 48 ms | 32 ms | −33% |
| `index_for_time` 6000 行二分 | 19 ms | 13 ms | −32% |
| 本地扫描 500 文件 | 463 ms | 287 ms | −38% |
| 主窗口冷启动 | 131 ms | 64 ms | −51% |
| 全量回归耗时 | ~2 s | 12.4 s | +×6（覆盖度扩展） |

## 打包产物

| 平台 | 文件 | 大小 | 生成方式 |
|---|---|---:|---|
| Linux amd64 | `netease-music-downloader_1.2.0_amd64.deb` | 48 MB | `packaging/build_deb.sh` |
| Windows | `NetEaseMusic.exe` | 45 MB | `packaging/build_exe.bat` |
| macOS | `NetEaseMusic-macOS.zip` | 32 MB | `packaging/build_mac.sh` |

安装方式：
- Linux: `sudo apt install ./netease-music-downloader_1.2.0_amd64.deb`
- Windows: 双击 `NetEaseMusic.exe`
- macOS: 解压后拖动 `NetEaseMusic.app` 到 `/Applications`

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python tests/selftest.py
```

## Release

- Tag: [`v1.2.0`](https://github.com/ClockworkParrot/NetEaseMusic/releases/tag/v1.2.0)
- Assets: 3 附件（deb / exe / zip）
- CI: 每 push/PR 跑 5 个矩阵 job（Linux × 2 py + Windows × 2 py + macOS × 1 py）
