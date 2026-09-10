@echo off
title Stop Smart Network Automation
echo Stopping the server...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /f /pid %%p >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo Done.
timeout /t 2 >nul
