@echo off
setlocal enabledelayedexpansion
title Record a Pole Position II session
rem ---------------------------------------------------------------------------
rem  Record a Pole Position II session to an .inp file.
rem
rem  MAME's a7800 driver reports savestate="unsupported", so .sta files cannot
rem  be restored. Input recording works instead: it replays your exact session
rem  deterministically from power-on.
rem
rem  Double-click for the next free run-NN.inp, or drag a name onto this file
rem  (or run it from a prompt with one) to choose the name yourself.
rem
rem  With no name it picks the next unused run-NN.inp, so a new recording can
rem  never overwrite an old one. Play to the point you want captured, then
rem  press Esc to stop.
rem ---------------------------------------------------------------------------
set "HERE=%~dp0"
cd /d "%HERE%"

set "BIOS=%HERE%..\bios"
set "CART=%HERE%Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"

rem ---- find MAME ------------------------------------------------------------
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

rem ---- pick a name ----------------------------------------------------------
set "NAME=%~1"
if "!NAME!"=="" (
  set /a N=1
  :next
  set "NN=0!N!"
  set "NN=!NN:~-2!"
  if exist "%HERE%run-!NN!.inp" (
    set /a N+=1
    goto :next
  )
  set "NAME=run-!NN!"
)

echo Recording to "!NAME!.inp"
echo Play to the point you want captured, then press Esc to stop.
echo.

"!MAME!" a7800 -rompath "%BIOS%" -cart "!CART!" -skip_gameinfo -window ^
  -input_directory "%HERE%." -record "!NAME!.inp"

echo.
if exist "%HERE%!NAME!.inp" (
  for %%A in ("%HERE%!NAME!.inp") do echo Saved: !NAME!.inp  ^(%%~zA bytes^)
) else (
  echo WARNING: no recording was written.
)

:finish
echo.
pause
endlocal
