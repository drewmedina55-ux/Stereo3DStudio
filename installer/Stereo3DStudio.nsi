; Stereo3D Studio - Windows setup wizard (NSIS 3, Modern UI 2)
;
; Build (Windows or Linux):  makensis -DVERSION=1.4 -DSRC=<staged package folder> installer/Stereo3DStudio.nsi
; The staged folder is the release package WITHOUT a models folder. The wizard copies the app, then runs
; installer\install.ps1 unattended (Python + PyTorch for this PC's GPU) and shows its output live.
; The models folder is never overwritten or removed by an install or update.

Unicode true
!ifndef VERSION
  !define VERSION "1.4.1"
!endif
!ifndef SRC
  !define SRC ".."
!endif
!define APP "Stereo3D Studio"
!define EXE "Stereo3DStudio.exe"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Stereo3DStudio"
!define APP_KEY "Software\Stereo3D Studio"

Name "${APP} ${VERSION}"
OutFile "Stereo3DStudio_v${VERSION}_Setup.exe"
; per-user install: no admin rights, and the app can write its models folder next to itself
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "${APP_KEY}" "InstallDir"
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show
BrandingText "${APP} ${VERSION} — by Drew Medina"

!ifndef VIVERSION
  !define VIVERSION "${VERSION}.0.0"   ; Windows wants four numbers: pass -DVIVERSION=1.4.1.0 for three-part versions
!endif
VIProductVersion "${VIVERSION}"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "${APP} setup"
VIAddVersionKey "CompanyName" "Drew Medina"
VIAddVersionKey "LegalCopyright" "Copyright (C) 2026 Drew Medina"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

!define MUI_ICON "${SRC}\assets\stereo3dstudio.ico"
!define MUI_UNICON "${SRC}\assets\stereo3dstudio.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "${SRC}\installer\wizard_side.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${SRC}\installer\wizard_side.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "${SRC}\installer\wizard_header.bmp"
!define MUI_HEADERIMAGE_BITMAP_STRETCH AspectFitHeight
!define MUI_ABORTWARNING
!define MUI_COMPONENTSPAGE_SMALLDESC

!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APP} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "${APP} turns 2D videos and pictures into 3D for the Samsung Odyssey 3D, 3D TVs and VR headsets, and makes depth maps.$\r$\n$\r$\nSetup copies the app, then downloads Python and PyTorch for your NVIDIA GPU (about 3 GB — usually 5 to 20 minutes).$\r$\n$\r$\nUpdating? Install into the same folder: your downloaded models are always kept."
!insertmacro MUI_PAGE_WELCOME
!define MUI_LICENSEPAGE_TEXT_TOP "${APP} is free for personal and other non-commercial use, and may not be sold."
!insertmacro MUI_PAGE_LICENSE "${SRC}\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APP}"
!define MUI_FINISHPAGE_LINK "Stereo3D Studio on GitHub"
!define MUI_FINISHPAGE_LINK_LOCATION "https://github.com/drewmedina55-ux/Stereo3DStudio"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Var SetupFailed

; ------------------------------------------------------------------------------------------------ install
Section "${APP} (required)" SecApp
  SectionIn RO
  SetShellVarContext current
  StrCpy $SetupFailed "0"

  ; refresh the program code on update so no outdated files linger — never the models folder
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\engine"
  RMDir /r "$INSTDIR\thirdparty"

  SetOutPath "$INSTDIR"
  File /r "${SRC}\*.*"
  CreateDirectory "$INSTDIR\models"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${APP_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "Drew Medina"
  WriteRegStr HKCU "${UNINST_KEY}" "URLInfoAbout" "https://github.com/drewmedina55-ux/Stereo3DStudio"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${EXE}"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" 7000000

  CreateShortCut "$SMPROGRAMS\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0 SW_SHOWNORMAL "" "2D to 3D converter"
SectionEnd

Section "Desktop shortcut" SecDesktop
  SetShellVarContext current
  CreateShortCut "$DESKTOP\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0 SW_SHOWNORMAL "" "2D to 3D converter"
SectionEnd

Section "Depth Anything V2 Large (1.3 GB)" SecLarge
  ; nothing here: the setup step below downloads it when this is ticked
SectionEnd

Section "-Runtime setup" SecRuntime
  ; Python + PyTorch + packages for this PC's GPU. install.ps1 never touches the models folder.
  StrCpy $0 "no"
  ${If} ${SectionIsSelected} ${SecLarge}
    StrCpy $0 "yes"
  ${EndIf}
  StrCpy $1 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"   ; 64-bit PowerShell
  ${IfNot} ${FileExists} "$1"
    StrCpy $1 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ${EndIf}
  DetailPrint "Setting up Python, PyTorch and the 3D engine for your GPU (5–20 minutes)…"
  DetailPrint "Details are also saved to $INSTDIR\install_log.txt"
  SetDetailsPrint both
  nsExec::ExecToLog '"$1" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installer\install.ps1" -Unattended -NoShortcuts -LargeModel $0'
  Pop $2
  ${If} $2 != "0"
    StrCpy $SetupFailed "1"
    DetailPrint "Setup step failed (code $2)."
    MessageBox MB_ICONEXCLAMATION|MB_OK "${APP} was copied, but setting up Python/PyTorch did not finish (code $2).$\r$\n$\r$\nCheck your internet connection and NVIDIA driver, then run Setup again — it repairs the install. If it keeps failing, send install_log.txt from the install folder."
  ${Else}
    DetailPrint "${APP} ${VERSION} is installed."
  ${EndIf}
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} "The app, the 3D engine and its GPU runtime (downloaded for your graphics card during setup)."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Put a ${APP} shortcut on the desktop."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecLarge} "The default depth model. Licensed CC BY-NC 4.0: personal / non-commercial use only. Untick to download it later from the Models window."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "${APP} needs 64-bit Windows 10 or 11."
    Abort
  ${EndIf}
FunctionEnd

; ------------------------------------------------------------------------------------------------ uninstall
Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}.lnk"

  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\engine"
  RMDir /r "$INSTDIR\thirdparty"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\runtime_python"
  RMDir /r "$INSTDIR\installer"
  RMDir /r "$INSTDIR\assets"
  Delete "$INSTDIR\${EXE}"
  Delete "$INSTDIR\*.bat"
  Delete "$INSTDIR\*.md"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\install_log.txt"
  Delete "$INSTDIR\Uninstall.exe"

  ; the models are large and reusable: keep them unless the user explicitly says otherwise
  ${If} ${FileExists} "$INSTDIR\models\*.*"
    MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Also delete your downloaded depth models?$\r$\n$\r$\n$INSTDIR\models$\r$\n$\r$\nChoose No to keep them for a future install." IDNO keep_models
    RMDir /r "$INSTDIR\models"
    keep_models:
  ${EndIf}
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "${UNINST_KEY}"
  DeleteRegKey HKCU "${APP_KEY}"
SectionEnd
