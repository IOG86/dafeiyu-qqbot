@echo off
chcp 65001 >nul
title 大肥鱼 QQ 机器人 - 控制台
set "KEY=%~dp0..\.ssh\your-key.pem"
set "HOST=root@203.0.113.10"
set "SSH=ssh -i "%KEY%" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ConnectTimeout=15"

:menu
cls
echo ==========================================================
echo            大肥鱼 QQ 机器人  控制台
echo ==========================================================
echo   [面板] AstrBot   http://127.0.0.1:6185   astrbot / change-me-panel
echo   [面板] SnowLuma http://127.0.0.1:5099   admin    / change-me-panel
echo   [桌面] noVNC     http://127.0.0.1:6081   密码 change-me-vnc
echo ----------------------------------------------------------
echo   1. 查看完整状态（QQ 是否在线 / 连接 / 资源）
echo   2. 重启 QQ（SnowLuma）
echo   3. 重启 AstrBot
echo   4. 全部重启
echo   5. 停止全部
echo   6. 启动全部
echo   7. 查看最近日志
echo   8. 刷新登录二维码
echo   9. 重开 SSH 隧道（新窗口）
echo   D. 诊断（最近错误）
echo   0. 退出
echo ==========================================================
set /p c=请输入编号后回车: 

if "%c%"=="1" goto do_status
if "%c%"=="2" goto do_qq
if "%c%"=="3" goto do_astrbot
if "%c%"=="4" goto do_restart
if "%c%"=="5" goto do_stop
if "%c%"=="6" goto do_start
if "%c%"=="7" goto do_logs
if "%c%"=="8" goto do_qr
if "%c%"=="9" goto do_tunnel
if /i "%c%"=="d" goto do_diag
if "%c%"=="0" exit
goto menu

:do_status
%SSH% "bash /opt/qqbot/ctl.sh status"
echo.
pause
goto menu

:do_qq
%SSH% "bash /opt/qqbot/ctl.sh qq"
echo.
pause
goto menu

:do_astrbot
%SSH% "bash /opt/qqbot/ctl.sh astrbot"
echo.
pause
goto menu

:do_restart
%SSH% "bash /opt/qqbot/ctl.sh restart"
echo.
pause
goto menu

:do_stop
%SSH% "bash /opt/qqbot/ctl.sh stop"
echo.
pause
goto menu

:do_start
%SSH% "bash /opt/qqbot/ctl.sh start"
echo.
pause
goto menu

:do_logs
%SSH% "bash /opt/qqbot/ctl.sh logs 120"
echo.
pause
goto menu

:do_qr
%SSH% "bash /opt/qqbot/ctl.sh qr"
echo 请在 noVNC 页面查看并扫码: http://127.0.0.1:6081
echo.
pause
goto menu

:do_tunnel
start "SSH 隧道" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tunnel.ps1"
goto menu

:do_diag
%SSH% "bash /opt/qqbot/ctl.sh check"
echo.
echo --- 看门狗日志 ---
%SSH% "tail -20 /var/log/io-watchdog.log 2>/dev/null"
echo.
pause
goto menu
