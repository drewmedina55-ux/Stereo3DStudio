@echo off
rem Starts Stereo3D Studio with a console window - useful for troubleshooting.
cd /d "%~dp0"
set "PYTHONPATH=%~dp0app;%~dp0engine"
set PYTHONNOUSERSITE=1
set PYTHONHOME=
"%~dp0runtime\Scripts\python.exe" -m stereo3dstudio %*
pause
