@echo off
title Stereo3D Studio 1.0 Setup
cd /d "%~dp0"
echo.
echo  Stereo3D Studio 1.0 - GPU setup
echo  This downloads Python + PyTorch (CUDA) + the 3D engine into this folder.
echo  Expect roughly 6-7 GB on disk and 5-20 minutes depending on your connection.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1" %*
echo.
pause
