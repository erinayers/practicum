@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Practicum Launcher

rem ===========================================================================
rem  start-practicum.bat  -  start the Practicum API and the desktop app together
rem
rem  Usage (double-click, or from a terminal in the repo root):
rem    start-practicum.bat            start the API + desktop app
rem    start-practicum.bat --dev      same, but the API auto-reloads on code changes
rem                                   (note: a reload restarts the API and clears its
rem                                   in-memory lab list)
rem    start-practicum.bat --setup    force (re)install of both packages into .venv first
rem    start-practicum.bat --help     show this text
rem
rem  What it does:
rem    1. Creates .venv and installs "practicum" + "practicum-desktop" if needed.
rem    2. Starts the API (uvicorn) in its own window, unless one is already healthy.
rem    3. Waits for GET /health to answer 200.
rem    4. Launches the desktop app in this window.
rem    5. When you close the desktop app, shuts the API window down again
rem       (only if this script started it).
rem
rem  Environment:
rem    PRACTICUM_API_PORT   API port (default 8000). The desktop app remembers its own
rem                         "API base URL" setting, so if you change the port here, also
rem                         change that field once in the app and press Retry.
rem ===========================================================================

cd /d "%~dp0"
set "ROOT=%CD%"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"
if not defined PRACTICUM_API_PORT set "PRACTICUM_API_PORT=8000"
set "API_PORT=%PRACTICUM_API_PORT%"
set "API_URL=http://127.0.0.1:%API_PORT%"
set "API_TITLE=Practicum API (port %API_PORT%)"
set "RELOAD="
set "FORCE_SETUP="
set "API_STARTED_HERE="
set "DESKTOP_EXIT=0"

rem ---- arguments -------------------------------------------------------------
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--dev"   set "RELOAD=--reload"
if /i "%~1"=="--setup" set "FORCE_SETUP=1"
if /i "%~1"=="--help"  goto usage
if /i "%~1"=="-h"      goto usage
if /i "%~1"=="/?"      goto usage
shift
goto parse_args
:args_done

echo.
echo  Practicum launcher
echo  root : %ROOT%
echo  api  : %API_URL%
echo.

rem ---- 1. virtual environment + packages ---------------------------------------
if defined FORCE_SETUP goto setup
if not exist "%PY%" goto setup
"%PY%" -c "import practicum, practicum_desktop, uvicorn, fastapi, PySide6, httpx" >nul 2>&1
if errorlevel 1 goto setup
goto venv_ready

:setup
echo [setup] Preparing virtual environment in "%VENV%" ...
if exist "%PY%" goto install
where py >nul 2>&1
if errorlevel 1 goto venv_with_python
py -3 -m venv "%VENV%"
goto venv_created
:venv_with_python
python -m venv "%VENV%"
:venv_created
if not exist "%PY%" (
    echo [error] Could not create a virtual environment.
    echo         Install Python 3.12 or newer from https://www.python.org/ and run this again.
    goto fail
)

:install
"%PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [error] The Python in .venv is older than 3.12. Delete the .venv folder and run again
    echo         with Python 3.12+ installed.
    goto fail
)
echo [setup] Upgrading pip ...
"%PY%" -m pip install --quiet --upgrade pip
echo [setup] Installing practicum ^(API^) ...
"%PY%" -m pip install --quiet -e ".[dev]"
if errorlevel 1 goto pip_fail
echo [setup] Installing practicum-desktop ^(PySide6 - this can take a while the first time^) ...
"%PY%" -m pip install --quiet -e ".\desktop[dev]"
if errorlevel 1 goto pip_fail
echo [setup] Done.

:venv_ready

rem ---- 2. API -----------------------------------------------------------------
call :health
if "!HEALTH!"=="200" (
    echo [api] An API is already answering at %API_URL% - reusing it.
    goto api_ready
)

echo [api] Health probe ^(%HEALTH_VIA%^) returned "!HEALTH!" - no healthy API yet.
call :port_owner
if defined PORT_PID (
    echo [warn] Something is already LISTENING on port %API_PORT% ^(PID !PORT_PID!^) but it is not
    echo        answering GET /health. The new API will fail to bind. Stop that process, or run
    echo        this script with a different port:   set PRACTICUM_API_PORT=8001
)

echo [api] Starting the Practicum API in a separate window ...
echo       %PY% -m uvicorn practicum.main:app --host 127.0.0.1 --port %API_PORT% %RELOAD%
start "%API_TITLE%" /D "%ROOT%" cmd /k ""%PY%" -m uvicorn practicum.main:app --host 127.0.0.1 --port %API_PORT% %RELOAD%"
set "API_STARTED_HERE=1"

set /a TRIES=0
:wait_api
call :health
if "!HEALTH!"=="200" goto api_ready
set /a TRIES+=1
if !TRIES! geq 30 (
    echo [error] The API did not become healthy within 30 seconds.
    echo         Look at the "%API_TITLE%" window for the error, fix it, and run this again.
    goto fail
)
echo [api] waiting... attempt !TRIES!/30 - health=!HEALTH!
timeout /t 1 /nobreak >nul
goto wait_api

:api_ready
echo.
echo [api] Healthy at %API_URL%  ^(probe via %HEALTH_VIA%^)
call :health_body
echo [api] GET /health body: !HEALTH_BODY!
if not defined API_STARTED_HERE echo [api] NOTE: this API was NOT started by this script - it was already running.
echo [api] Interactive docs: %API_URL%/docs
echo [api] The desktop app connects to the "API base URL" it remembers ^(default %API_URL%^).
echo       If the app shows "Blocked", set that field to %API_URL% and press Retry.

rem ---- 3. Desktop app ---------------------------------------------------------
echo.
echo [desktop] Launching Practicum Desktop. Close the app window to shut everything down.
echo.
"%PY%" -m practicum_desktop.main
set "DESKTOP_EXIT=%ERRORLEVEL%"

rem ---- 4. Shutdown ------------------------------------------------------------
if defined API_STARTED_HERE (
    echo [api] Stopping the API window ...
    taskkill /FI "WINDOWTITLE eq Practicum API*" /T /F >nul 2>&1
)
echo [done] Practicum closed.
endlocal & exit /b %DESKTOP_EXIT%


rem ---- helpers ----------------------------------------------------------------
:health
rem Sets HEALTH to the HTTP status of GET /health ("000"/"0" when unreachable) and
rem HEALTH_VIA to the tool used.
set "HEALTH=0"
where curl.exe >nul 2>&1
if errorlevel 1 goto health_ps
set "HEALTH_VIA=curl"
for /f %%c in ('curl.exe -s -o NUL -w "%%{http_code}" --max-time 2 "%API_URL%/health" 2^>NUL') do set "HEALTH=%%c"
exit /b 0
:health_ps
set "HEALTH_VIA=powershell"
for /f %%c in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '%API_URL%/health' -TimeoutSec 2).StatusCode } catch { 0 }"') do set "HEALTH=%%c"
exit /b 0

:health_body
rem Sets HEALTH_BODY to the response text of GET /health (expect {"status":"ok"}).
set "HEALTH_BODY=(unavailable)"
where curl.exe >nul 2>&1
if errorlevel 1 goto health_body_ps
for /f "delims=" %%b in ('curl.exe -s --max-time 2 "%API_URL%/health" 2^>NUL') do set "HEALTH_BODY=%%b"
exit /b 0
:health_body_ps
for /f "delims=" %%b in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '%API_URL%/health' -TimeoutSec 2).Content } catch { '(error)' }"') do set "HEALTH_BODY=%%b"
exit /b 0

:port_owner
rem Sets PORT_PID to the PID listening on API_PORT (IPv4 loopback or any), if any.
set "PORT_PID="
for /f "tokens=5" %%p in ('netstat -ano -p TCP 2^>NUL ^| findstr /R /C:":%API_PORT% .*LISTENING"') do if not defined PORT_PID set "PORT_PID=%%p"
exit /b 0

:pip_fail
echo [error] pip install failed - see the output above.
:fail
echo.
pause
endlocal & exit /b 1

:usage
echo.
echo  start-practicum.bat [--dev] [--setup] [--help]
echo.
echo    (no options)  create .venv / install if needed, start the API, then the desktop app
echo    --dev         start the API with --reload (restarts on code changes; clears labs)
echo    --setup       force reinstall of both packages into .venv before starting
echo.
echo  Set PRACTICUM_API_PORT to use a port other than 8000.
echo.
endlocal & exit /b 0
