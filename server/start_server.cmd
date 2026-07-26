@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   MCJM Backend Server
echo ============================================
echo.
echo Checking Python...

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH!
    pause
    exit /b 1
)

echo Installing dependencies (first time only)...
python -m pip install -q flask jmcomic pillow 2>&1

echo.
echo Starting server on http://127.0.0.1:28374
echo Keep this window open while playing Minecraft!
echo.
python -u server.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server crashed. Check the error above.
    pause
)
