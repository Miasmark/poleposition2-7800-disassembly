@echo off
setlocal enabledelayedexpansion
title Play a Pole Position II recording
rem ---------------------------------------------------------------------------
rem  Watch a recorded Pole Position II session play back.
rem
rem  Double-click and type the recording name when asked, or drag one onto
rem  this file, or run it from a prompt with the name as an argument.
rem
rem  While watching:  P pauses,  Esc quits,  Tab opens the MAME menu.
rem  When the recording runs out the game carries on under your control.
rem ---------------------------------------------------------------------------
set "HERE=%~dp0"
cd /d "%HERE%"

set "BIOS=%HERE%..\bios"
set "CART=%HERE%Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"

set "MAME=%LOCALAPPDATA%\Programs\MAME\mame.exe"
if not exist "!MAME!" set "MAME=C:\Program Files\MAME\mame.exe"
if not exist "!MAME!" set "MAME=%HERE%..\a7800-win-v5.2\a7800.exe"
if not exist "!MAME!" (
  echo Could not find MAME. Install it, or edit MAME in this batch file.
  goto :finish
)
if not exist "!CART!" (
  echo Could not find the cartridge at:
  echo    !CART!
  echo.
  echo This project ships no ROM. Supply your own legally-owned dump, named
  echo exactly as above, in this folder.
  goto :finish
)

rem A dragged file arrives as a full path; take just its base name.
set "NAME=%~n1"
if "!NAME!"=="" (
  echo Recordings available:
  set "ANY="
  for %%F in ("%HERE%*.inp") do (
    echo    %%~nF
    set "ANY=1"
  )
  if not defined ANY (
    echo    ^(none yet -- use "Record Session.bat" first^)
    goto :finish
  )
  echo.
  set /p "NAME=Recording name (without .inp): "
)
if "!NAME!"=="" goto :finish
if not exist "%HERE%!NAME!.inp" (
  echo No such recording: !NAME!.inp
  goto :finish
)

echo Recording: !NAME!.inp
echo P pauses, Esc quits.
echo.

"!MAME!" a7800 -rompath "%BIOS%" -cart "!CART!" -skip_gameinfo -window ^
  -input_directory "%HERE%." -playback "!NAME!.inp"

:finish
echo.
pause
endlocal
