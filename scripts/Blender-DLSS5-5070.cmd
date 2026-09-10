@echo off
setlocal
rem Unified addon viewport/render path; do not inject the legacy screen ReShade.
set "DLSS5_BLENDER=C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
if not exist "%DLSS5_BLENDER%" (
  echo Blender Steam was not found. Open your installed Blender with the cycles_dlss5 addon enabled.
  pause
  exit /b 1
)
start "" "%DLSS5_BLENDER%" --disable-autoexec %*
endlocal
