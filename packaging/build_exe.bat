@echo off
REM ============================================================
REM  Windows 一键打包 exe
REM  前置: 已安装 Python 3.10+，然后执行:
REM      pip install -r requirements.txt pyinstaller pysocks
REM  产物: dist\NetEaseMusic.exe（单文件，免安装）
REM ============================================================
cd /d "%~dp0\.."

python -m PyInstaller --noconfirm --clean --noconsole --onefile ^
  --name NetEaseMusic ^
  --icon packaging\icon.ico ^
  --hidden-import socks --hidden-import sockshandler ^
  main.py

echo.
echo 完成: dist\NetEaseMusic.exe
pause
