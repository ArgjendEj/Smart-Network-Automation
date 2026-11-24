@echo off
cd /d "%~dp0"

REM --- install the Python packages once (first run only) ---
if not exist "backend\.venv\Scripts\python.exe" goto install
if exist "backend\.venv\.incomplete" goto install
goto installed

:install
set "PYCMD="
for %%v in (3.13 3.12 3.11) do if not defined PYCMD py -%%v -c "" >nul 2>&1 && set "PYCMD=py -%%v"
if not defined PYCMD python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD goto nopython
echo First run: installing the Python packages, please wait ^(1-3 minutes^)...
if not exist "backend\.venv\Scripts\python.exe" %PYCMD% -m venv "backend\.venv"
if not exist "backend\.venv\Scripts\python.exe" goto pipfailed
echo installing> "backend\.venv\.incomplete"
"backend\.venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 goto pipfailed
del "backend\.venv\.incomplete"

:installed
REM --- build the web interface once (first run only) ---
if exist "frontend\dist\index.html" goto built
where npm >nul 2>&1
if errorlevel 1 goto nonode
echo First run: building the interface, please wait ^(~30 seconds^)...
pushd frontend
if not exist "node_modules" call npm install
call npm run build
popd
if not exist "frontend\dist\index.html" goto buildfailed

:built
REM --- start the server hidden if it is not already running ---
cscript //nologo "%~dp0server.vbs"

REM --- wait until it answers, then open the browser ---
echo Opening the app...
set /a n=0
:wait
set /a n+=1
>nul ping -n 2 127.0.0.1
powershell -NoProfile -Command "try{if((Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2).status -eq 'ok'){exit 0}}catch{}; exit 1"
if errorlevel 1 if %n% LSS 20 goto wait

start "" http://localhost:8000
exit /b

:nopython
echo.
echo Python was not found. Install Python 3.13 from https://www.python.org/downloads/
echo and run start.bat again.
goto stop
:nonode
echo.
echo Node.js was not found. Install it from https://nodejs.org/ and run start.bat again.
goto stop
:pipfailed
echo.
echo The Python packages could not be installed. Check the internet connection, use
echo Python 3.11 - 3.13, keep the project in a short path, then run start.bat again.
goto stop
:buildfailed
echo.
echo The interface could not be built. Read the message above, then run start.bat again.
:stop
pause
exit /b 1
