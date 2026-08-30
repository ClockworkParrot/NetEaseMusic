#!/usr/bin/env bash
# macOS 一键打包 .app
# 前置: pip3 install -r requirements.txt pyinstaller pysocks
# 产物: dist/NetEaseMusic.app
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build

echo "==> [1/2] 生成 .icns 图标（sips/iconutil 为 macOS 自带）"
ICON_ARGS=""
if command -v iconutil >/dev/null 2>&1 && command -v sips >/dev/null 2>&1; then
    ICONSET="build/icon.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"
    for s in 16 32 64 128 256 512; do
        sips -z "$s" "$s" packaging/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
        d=$((s * 2))
        sips -z "$d" "$d" packaging/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o build/icon.icns
    ICON_ARGS="--icon build/icon.icns"
    echo "    build/icon.icns 已生成"
else
    echo "    未找到 sips/iconutil，跳过自定义图标"
fi

echo "==> [2/2] PyInstaller 打包 .app"
python3 -m PyInstaller --noconfirm --clean --windowed \
    --name NetEaseMusic \
    --hidden-import socks --hidden-import sockshandler \
    $ICON_ARGS \
    main.py

echo "完成: dist/NetEaseMusic.app"
