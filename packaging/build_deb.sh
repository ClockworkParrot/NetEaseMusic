#!/usr/bin/env bash
# 本地 Linux 构建 .deb 包
# 用法: bash packaging/build_deb.sh [版本号]        （默认 1.0.0）
#       PYTHON=.venv-build/bin/python3 bash packaging/build_deb.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-1.0.0}"
APP_NAME="netease-music"
PKG_NAME="${APP_NAME}-downloader"
PY="${PYTHON:-python3}"
# 中间组装目录放 /tmp：避免与项目内构建产物互相覆盖，也规避部分环境的删除限制
BUILD_DIR="${BUILD_DIR:-/tmp/netease-music-deb-root}"

if ! "$PY" -c "import PyInstaller" 2>/dev/null; then
    echo "错误: 未安装 PyInstaller，请先执行: $PY -m pip install pyinstaller"
    exit 1
fi

if [ "${SKIP_PYINSTALLER:-0}" != "1" ]; then
    echo "==> [1/4] PyInstaller 打包"
    "$PY" -m PyInstaller --noconfirm --clean --windowed \
        --name "${APP_NAME}" \
        --hidden-import socks --hidden-import sockshandler \
        main.py
else
    echo "==> [1/4] 跳过 PyInstaller（SKIP_PYINSTALLER=1，复用已有 dist/）"
fi

echo "==> [2/4] 组装 deb 目录树"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/DEBIAN" \
         "${BUILD_DIR}/opt/${APP_NAME}" \
         "${BUILD_DIR}/usr/bin" \
         "${BUILD_DIR}/usr/share/applications" \
         "${BUILD_DIR}/usr/share/icons/hicolor/256x256/apps"

cp -a "dist/${APP_NAME}/." "${BUILD_DIR}/opt/${APP_NAME}/"

INSTALLED_SIZE="$(du -sk "${BUILD_DIR}/opt" | cut -f1)"
cat > "${BUILD_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: sound
Priority: optional
Architecture: amd64
Installed-Size: ${INSTALLED_SIZE}
Depends: libgl1, libegl1, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libfontconfig1, libglib2.0-0, libgstreamer1.0-0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good
Maintainer: ClockworkParrot <clockworkparrot@users.noreply.github.com>
Homepage: https://github.com/ClockworkParrot
Description: 网易云音乐下载器（仿官方 UI）
 支持歌单/专辑/单曲链接解析、关键词搜索、
 多线程下载（歌词/封面嵌入）、本地试听播放。
EOF

cat > "${BUILD_DIR}/usr/bin/${APP_NAME}" <<EOF
#!/bin/bash
exec /opt/${APP_NAME}/${APP_NAME} "\$@"
EOF
chmod +x "${BUILD_DIR}/usr/bin/${APP_NAME}"

cp packaging/netease-music.desktop "${BUILD_DIR}/usr/share/applications/"
cp packaging/icon.png "${BUILD_DIR}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"

echo "==> [3/4] dpkg-deb 打包"
mkdir -p dist_deb 2>/dev/null || "$PY" -c "import pathlib; pathlib.Path('dist_deb').mkdir(exist_ok=True)"
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "dist_deb/${PKG_NAME}_${VERSION}_amd64.deb"

echo "==> [4/4] 完成: dist_deb/${PKG_NAME}_${VERSION}_amd64.deb"
echo "    安装: sudo apt install ./dist_deb/${PKG_NAME}_${VERSION}_amd64.deb"
