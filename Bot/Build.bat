@echo off
REM ==========================================================================
REM   RAPTECH DICEBOT - ONE-CLICK BUILD
REM ==========================================================================
REM   Tinggal double-click file ini setiap kali habis update source code.
REM
REM   Pemakaian (opsional, bisa digabung):
REM       Build.bat                 build onedir (default, direkomendasikan)
REM       Build.bat --onefile       single exe (startup lebih lambat)
REM       Build.bat --deps          install/update dependency dulu, lalu build
REM       Build.bat --clean         hapus output lama sebelum build (fresh)
REM       Build.bat --run           jalankan exe setelah build sukses
REM       Build.bat --help          tampilkan bantuan
REM
REM   Output: builds\desktop\raptech-dicebot.exe  (+ _internal\)
REM ==========================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
pushd "%ROOT%"

set "APP_NAME=raptech-dicebot"
set "OUT_DIR=%ROOT%\builds\desktop"
set "BUILD_PY=%ROOT%\scripts\build\build_desktop.py"

set "MODE="
set "MODE_LABEL=onedir"
set "DO_DEPS=0"
set "DO_CLEAN=0"
set "DO_RUN=0"

REM ---------------------------------------------------------------- args ----
:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--onefile" (
  set "MODE=--onefile"
  set "MODE_LABEL=onefile"
  shift
  goto parse
)
if /i "%~1"=="--deps" (
  set "DO_DEPS=1"
  shift
  goto parse
)
if /i "%~1"=="--clean" (
  set "DO_CLEAN=1"
  shift
  goto parse
)
if /i "%~1"=="--run" (
  set "DO_RUN=1"
  shift
  goto parse
)
if /i "%~1"=="--help" goto usage
if /i "%~1"=="-h" goto usage
if /i "%~1"=="/?" goto usage
echo [ERROR] Argumen tidak dikenal: %~1
goto usage
:parsed
echo ==========================================================
echo   RAPTECH DICEBOT - BUILD
echo ==========================================================
echo   Root   : %ROOT%
echo   Mode   : %MODE_LABEL%
echo   Output : %OUT_DIR%
echo   Mulai  : %DATE% %TIME%
echo ==========================================================
echo.

REM ------------------------------------------------------------ prasyarat ---
if not exist "%ROOT%\corebot\__init__.py" (
  echo [ERROR] folder corebot\ tidak ada / tidak lengkap.
  echo         Engine wajib ada sebelum build. Salin dulu dari sumber.
  goto fail
)
if not exist "%ROOT%\desktop\app.py" (
  echo [ERROR] desktop\app.py tidak ditemukan.
  goto fail
)
if not exist "%ROOT%\assets\icon.ico" (
  echo [ERROR] assets\icon.ico tidak ditemukan.
  goto fail
)
if not exist "%BUILD_PY%" (
  echo [ERROR] build script tidak ditemukan: %BUILD_PY%
  goto fail
)

REM --------------------------------------------------------------- python ---
set "PY="
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python tidak ditemukan di PATH. Install Python 3.10+ dulu.
  goto fail
)
for /f "delims=" %%V in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set "PYVER=%%V"
echo [1/5] Python terdeteksi: %PY%  ^(versi %PYVER%^)

REM ----------------------------------------------------------------- deps ---
if "%DO_DEPS%"=="1" (
  echo [2/5] Install/update dependency...
  %PY% -m pip install --upgrade pip
  if exist "%ROOT%\requirements.txt" %PY% -m pip install -r "%ROOT%\requirements.txt"
  if errorlevel 1 goto deps_fail
  if exist "%ROOT%\desktop\requirements-desktop.txt" %PY% -m pip install -r "%ROOT%\desktop\requirements-desktop.txt"
  if errorlevel 1 goto deps_fail
) else (
  echo [2/5] Skip install dependency ^(pakai --deps kalau perlu update^)
)

echo       Cek PyInstaller...
%PY% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo       PyInstaller belum ada - install sekarang...
  %PY% -m pip install pyinstaller
  if errorlevel 1 goto deps_fail
)

REM -------------------------------------------- backup token + clean out ---
set "TOKEN_BAK="
if exist "%OUT_DIR%\apitokens.json" (
  set "TOKEN_BAK=%TEMP%\raptech_apitokens_backup.json"
  copy /Y "%OUT_DIR%\apitokens.json" "!TOKEN_BAK!" >nul
)

if "%DO_CLEAN%"=="1" (
  echo [3/5] Bersihkan output lama...
  if exist "%OUT_DIR%" rmdir /S /Q "%OUT_DIR%"
  if exist "%ROOT%\builds\_pyinstaller_tmp" rmdir /S /Q "%ROOT%\builds\_pyinstaller_tmp"
  if exist "%ROOT%\builds\%APP_NAME%" rmdir /S /Q "%ROOT%\builds\%APP_NAME%"
  if exist "%ROOT%\builds\%APP_NAME%.spec" del /Q "%ROOT%\builds\%APP_NAME%.spec"
) else (
  echo [3/5] Skip clean ^(pakai --clean untuk fresh build^)
)

REM ---------------------------------------------------------------- build ---
echo [4/5] PyInstaller build...
echo.
%PY% "%BUILD_PY%" %MODE%
if errorlevel 1 (
  echo.
  echo [ERROR] Build GAGAL. Cek pesan error di atas.
  echo         Tips: jalankan  Build.bat --deps --clean
  goto restore_fail
)

if not exist "%OUT_DIR%\%APP_NAME%.exe" (
  echo.
  echo [ERROR] Build selesai tapi %APP_NAME%.exe tidak ditemukan di output.
  goto restore_fail
)

REM ------------------------------------------------------- restore token ---
if defined TOKEN_BAK (
  if exist "%TOKEN_BAK%" (
    copy /Y "%TOKEN_BAK%" "%OUT_DIR%\apitokens.json" >nul
    del /Q "%TOKEN_BAK%" >nul 2>nul
    echo       apitokens.json lama dipulihkan.
  )
)

REM ---------------------------------------------------------------- hasil ---
echo.
echo [5/5] Verifikasi output...
for %%F in ("%OUT_DIR%\%APP_NAME%.exe") do set /a EXE_KB=%%~zF/1024
echo       raptech-dicebot.exe : !EXE_KB! KB
if exist "%OUT_DIR%\_internal" (
  echo       _internal\          : OK
) else (
  if "%MODE_LABEL%"=="onedir" echo       [WARNING] folder _internal\ tidak ada - exe bisa gagal jalan.
)
if exist "%OUT_DIR%\strategies\sample.lua" (
  echo       strategies\         : OK
) else (
  echo       [WARNING] strategies\sample.lua tidak ter-bundle.
)

echo.
echo ==========================================================
echo   BUILD SUKSES  -  %DATE% %TIME%
echo   %OUT_DIR%\%APP_NAME%.exe
echo ==========================================================
echo.
echo   Sebelum distribusi: kosongkan apitokens.json.
echo.

if "%DO_RUN%"=="1" (
  echo Menjalankan aplikasi...
  start "" "%OUT_DIR%\%APP_NAME%.exe"
) else (
  choice /C YN /N /T 15 /D N /M "Buka folder output sekarang? [Y/N] "
  if not errorlevel 2 start "" explorer "%OUT_DIR%"
)

popd
endlocal
exit /b 0

REM ========================================================== error paths ===
:deps_fail
echo.
echo [ERROR] Install dependency gagal. Cek koneksi internet / versi Python.
goto fail

:restore_fail
if defined TOKEN_BAK (
  if exist "%TOKEN_BAK%" (
    if exist "%OUT_DIR%" copy /Y "%TOKEN_BAK%" "%OUT_DIR%\apitokens.json" >nul 2>nul
    del /Q "%TOKEN_BAK%" >nul 2>nul
  )
)
goto fail

:usage
echo.
echo   Build.bat [--onefile] [--deps] [--clean] [--run]
echo.
echo     --onefile   Bundle jadi 1 file exe ^(startup lebih lambat^)
echo     --deps      Install/update dependency sebelum build
echo     --clean     Hapus builds\desktop lama dulu ^(fresh build^)
echo     --run       Langsung jalankan exe setelah build sukses
echo.
echo   Contoh update rutin  : Build.bat
echo   Contoh rilis bersih  : Build.bat --deps --clean
echo.
popd
endlocal
exit /b 0

:fail
echo.
pause
popd
endlocal
exit /b 1
