@echo off
setlocal
"%~dp0blender.exe" --python-exit-code 1 --python "%~dp0start_portable.py" %*
if errorlevel 1 pause

