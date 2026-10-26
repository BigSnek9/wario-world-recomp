@echo off
setlocal
set "MODERNGEKKO_STATICRECOMP=1"
set "STATICRECOMP_LOCKSTEP="
set "project_dir=%~dp0"
if not exist "%project_dir%build\moderngekko\Release\moderngekko-run.exe" (
  echo Build the ModernGekko runtime first.
  exit /b 2
)
rem Prefer the clang-built module (same generated code, ~1.75x faster, lockstep-verified
rem 2026-10-26). Set WARIO_MODULE=msvc to use the original MSVC build instead.
set "game_module=%project_dir%build\module-full-vectors-clang\gGWWE01_recomp.dll"
if /i "%WARIO_MODULE%"=="msvc" set "game_module=%project_dir%build\module-full-vectors\Release\gGWWE01_recomp.dll"
if not exist "%game_module%" set "game_module=%project_dir%build\module-full-vectors\Release\gGWWE01_recomp.dll"
if not exist "%game_module%" (
  echo Build the full vector-inclusive game module first.
  exit /b 2
)
if not exist "%project_dir%original\GWWE01\sys\main.dol" (
  echo The user's extracted GWWE01 game is missing.
  exit /b 2
)
if not exist "%project_dir%private" mkdir "%project_dir%private"
if not exist "%project_dir%private\playtest-user\Config\GCPadNew.ini" (
  python "%project_dir%scripts\configure_controls.py" --user-dir "%project_dir%private\playtest-user" > "%project_dir%private\controls-setup.log" 2>&1
  if errorlevel 1 (
    type "%project_dir%private\controls-setup.log"
    pause
    exit /b 3
  )
)
python "%project_dir%scripts\configure_baseline.py" --user-dir "%project_dir%private\playtest-user" > "%project_dir%private\baseline-setup.log" 2>&1
if errorlevel 1 (
  type "%project_dir%private\baseline-setup.log"
  pause
  exit /b 4
)
pushd "%project_dir%build\moderngekko\Release"
"%project_dir%build\moderngekko\Release\moderngekko-run.exe" --game "%project_dir%original\GWWE01" --module "%game_module%" --user-dir "%project_dir%private\playtest-user" --graphics OpenGL --no-mods --title "Wario World Recomp - Test Build" > "%project_dir%private\playtest-last.log" 2>&1
set "playtest_exit=%ERRORLEVEL%"
popd
if not "%playtest_exit%"=="0" (
  type "%project_dir%private\playtest-last.log"
  pause
)
exit /b %playtest_exit%
