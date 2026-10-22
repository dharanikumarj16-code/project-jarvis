@echo off
REM ==============================================================================
REM start_jarvis.bat - Double-Click Windows Launcher for JARVIS
REM ==============================================================================
title JARVIS OS - Windows AI Automation
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_jarvis.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [JARVIS] Execution ended with code %ERRORLEVEL%.
    pause
)
