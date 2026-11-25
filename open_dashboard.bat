@echo off
setlocal
title Forge Lead Studio — Dashboard Launcher
cd /d c:\agencia

echo ============================================================================
echo   FORGE LEAD STUDIO — ZERO-TOKEN EXECUTIVE COMMAND CENTER
echo ============================================================================
echo.

netstat -ano | findstr ":8787 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [INFO] Local dashboard server already running on http://localhost:8787
) else (
  echo [INFO] Starting local Python HTTP server on http://localhost:8787 ...
  start "Forge Lead Studio Server (Port 8787)" /min cmd /k "cd /d c:\agencia && python -m http.server 8787 --bind 127.0.0.1"
  timeout /t 2 /nobreak >nul
)

echo [INFO] Opening http://localhost:8787/dashboard.html in default browser...
start "" "http://localhost:8787/dashboard.html"
echo [OK  ] Command center launched. Keep the minimized server window open for 10s live auto-refresh.
endlocal
exit /b 0
