@echo off
cd /d "%~dp0"

REM --- build the web interface once (first run only) ---
if not exist "frontend\dist\index.html" (
  echo First run: building the interface, please wait ^(~30 seconds^)...
  pushd frontend
  if not exist "node_modules" call npm install
  call npm run build
  popd
)

REM --- start the server hidden if it is not already running ---
cscript //nologo "%~dp0server.vbs"

REM --- wait until it answers, then open the browser ---
echo Opening the app...
set /a n=0
:wait
set /a n+=1
>nul ping -n 2 127.0.0.1
powershell -NoProfile -Command "try{if((Invoke-RestMethod http://localhost:8000/api/health -TimeoutSec 2).status -eq 'ok'){exit 0}}catch{}; exit 1"
if errorlevel 1 if %n% LSS 20 goto wait

start "" http://localhost:8000
exit /b
