@echo off
chcp 65001 >nul
title 大肥鱼 - 一键启动
cd /d "%~dp0"

echo ============================================
echo   大肥鱼 - 一键启动
echo ============================================
echo.
echo   [1/2] 启动 SSH 隧道（最小化窗口，别关）...
start "SSH隧道" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\tunnel.ps1"

echo   [2/2] 等待 3 秒后启动控制台...
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8090
cd /d "%~dp0console"
py -3 -u app.py
if errorlevel 1 python app.py

echo.
echo 控制台已退出。隧道窗口可以手动关闭。
pause
