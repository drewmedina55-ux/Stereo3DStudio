@echo off
title Uninstall Stereo3D Studio
cd /d "%~dp0"
echo This removes the Stereo3D Studio runtime and shortcuts.
echo Your converted videos are not touched.
choice /M "Also delete downloaded depth models (models folder) and settings"
set DELMODELS=%errorlevel%
del "%USERPROFILE%\Desktop\Stereo3D Studio.lnk" 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Stereo3D Studio.lnk" 2>nul
if exist "%~dp0runtime" rmdir /s /q "%~dp0runtime"
if exist "%~dp0runtime_python" rmdir /s /q "%~dp0runtime_python"
if exist "%~dp0installer\tools" rmdir /s /q "%~dp0installer\tools"
if "%DELMODELS%"=="1" (
  rmdir /s /q "%LOCALAPPDATA%\Stereo3DStudio" 2>nul
  if exist "%~dp0models" rmdir /s /q "%~dp0models"
  rmdir /s /q "%APPDATA%\Stereo3DStudio" 2>nul
)
echo Done. You can now delete this folder.
pause
