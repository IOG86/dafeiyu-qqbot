@echo off
chcp 65001 >nul
title QQ Bot SSH Tunnel
echo ============================================
echo   QQ Bot - SSH Tunnel (AstrBot / SnowLuma / noVNC)
echo ============================================
echo.
echo   AstrBot  : http://127.0.0.1:6185
echo   SnowLuma : http://127.0.0.1:5099
echo   noVNC    : http://127.0.0.1:6081
echo.
echo   Keep this window open. Close it to stop the tunnel.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tunnel.ps1"
pause
