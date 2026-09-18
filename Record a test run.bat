@echo off
setlocal enabledelayedexpansion
title Pole Position II split-screen -- test run recorder
rem ---------------------------------------------------------------------------
rem  Record a play session of a split-screen build so it can be replayed and
rem  measured frame by frame.
rem
rem  Drag any .a78 onto this file, or double-click to record patches\pp2-2p.a78.
rem
rem  MAME opens as normal. Drive, then close MAME. The recording lands in this
rem  folder next to run-01.inp and run-02.inp, which is where the measuring
rem  scripts look for it.
rem
rem  ## Player 2
rem
rem  Player 2 drives on the SECOND controller: stick up accelerates, down
rem  brakes, left and right steer. The game itself never reads that stick --
rem  the split-screen patch does -- so nothing else in the game responds to it.
rem
rem  ## One recording per build
rem
rem  A recording is button states against frame numbers, not intentions. Replay
rem  it on a build whose timing differs and the same presses land at different
rem  moments, and the race goes somewhere else entirely. So record a fresh
rem  session on each build rather than reusing one across builds. That is also
rem  why a recording cannot prove a build "matches" an older one; it can only
rem  show the build stays healthy.
rem ---------------------------------------------------------------------------

set "HERE=%~dp0"
rem %~dp0 ends with a backslash, and "...\" escapes the closing quote on a
rem Windows command line, silently mangling every argument after it -- an
rem earlier recorder in this project recorded nothing for exactly that reason,
rem because MAME never saw -record. DIR is the same path without the trailing
rem backslash, for quoted use.
set "DIR=%HERE:~0,-1%"
set "BIOS=%DIR%\..\bios"

set "CART=%~1"
if not "%CART%"=="" goto :gotcart
set "CART=%DIR%\patches\pp2-2p.a78"
if exist "!CART!" goto :gotcart
echo Nothing was dropped on this file, and patches\pp2-2p.a78 is not built.
echo Drag a .a78 onto this batch file.
goto :finish

:gotcart
if not exist "!CART!" (
  echo Not there: !CART!
  goto :finish
)

rem Timestamp the name so repeated runs never overwrite each other. WMIC gives
rem a locale-independent stamp; the date command's format changes per machine.
set "STAMP="
for /f %%T in ('wmic os get localdatetime ^| findstr /r "^[0-9]"') do if not defined STAMP set "STAMP=%%T"
if not defined STAMP set "STAMP=manual"
set "STAMP=!STAMP:~4,4!-!STAMP:~8,4!"
for %%F in ("!CART!") do set "NAME=%%~nF"
set "INP=test-!NAME!-!STAMP!.inp"

set "MAME=%LOCALAPPDATA%\Programs\MAME\mame.exe"
if not exist "!MAME!" set "MAME=C:\Program Files\MAME\mame.exe"
if not exist "!MAME!" (
  echo Could not find MAME. Edit MAME in this batch file.
  goto :finish
)

echo   cartridge:  !CART!
echo   recording:  !INP!
echo.
echo   Player 1 is the first controller, player 2 the second.
echo   Drive for a minute or two. Close MAME when you are done.
echo.
pause

"!MAME!" a7800 -rompath "%BIOS%" -cart "!CART!" ^
    -input_directory "%DIR%" -record "!INP!" -window -skip_gameinfo

echo.
if exist "%DIR%\!INP!" (
  for %%F in ("%DIR%\!INP!") do echo   Saved: !INP!  ^(%%~zF bytes^)
  echo.
  echo   Replay it with:
  echo     mame a7800 -rompath ..\bios -cart "!CART!" -skip_gameinfo ^
-input_directory "%DIR%" -playback !INP!
) else (
  echo   No recording was written. If MAME reported an error above, that is why.
)

:finish
echo.
pause
endlocal
