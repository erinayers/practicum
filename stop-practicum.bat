@echo off
rem ===========================================================================
rem  stop-practicum.bat  -  stop an API window left behind by start-practicum.bat
rem  (Normally not needed: closing the desktop app stops the API automatically.)
rem ===========================================================================
echo Stopping any "Practicum API" window ...
taskkill /FI "WINDOWTITLE eq Practicum API*" /T /F
echo.
echo If labs are still running in Docker, stop or reset them from the app,
echo or run:  docker ps --filter "label=practicum.lab_id"
pause
