@echo off
setlocal

:: Guarantee standard Windows System32, PowerShell, and Python/uv paths are in PATH
set "PATH=%SystemRoot%\System32;%SystemRoot%\System32\WindowsPowerShell\v1.0;%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts;%PATH%"

cd /d "%~dp0\.."

echo ========================================
echo        ForeSight Local Launcher
echo ========================================
echo Working Directory: %CD%

:: Clean up accidental 0-byte redirect files if present
if exist "uv" if not exist "uv.exe" if not exist "uv.bat" del /f /q "uv" >nul 2>nul
if exist "Copy-Item" del /f /q "Copy-Item" >nul 2>nul

if "%DECISIONIQ_PORT%"=="" set DECISIONIQ_PORT=8082
if "%INSTALL_PHISHING%"=="" set INSTALL_PHISHING=1
if "%INSTALL_DEMO_DATA%"=="" set INSTALL_DEMO_DATA=1

:: 1. Frontend Check & Build
if exist "frontend\dist\index.html" (
    echo.
    echo [1/4] Frontend build already present in frontend\dist. Skipping build.
    echo       ^(To force rebuild, delete the frontend\dist folder^)
    goto :frontend_done
)

echo.
echo [1/4] Installing frontend dependencies and building dashboard...
call npm --prefix frontend install
if errorlevel 1 (
    echo [ERROR] Failed to install frontend packages.
    pause
    exit /b 1
)
call npm --prefix frontend run build
if errorlevel 1 (
    echo [ERROR] Failed to build frontend.
    pause
    exit /b 1
)

:frontend_done

:: 2. Find or Install uv
set "UV_RUNNER="

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV_RUNNER=uv"
    goto :uv_ready
)

if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
    set "UV_RUNNER=uv"
    goto :uv_ready
)

where uv >nul 2>nul
if %errorlevel% equ 0 (
    set "UV_RUNNER=uv"
    goto :uv_ready
)

python -m uv --version >nul 2>nul
if %errorlevel% equ 0 (
    set "UV_RUNNER=python -m uv"
    goto :uv_ready
)

echo.
echo [Notice] 'uv' was not found on your system.
echo Downloading and installing uv (Astral Python manager)...

if exist "%SystemRoot%\System32\curl.exe" (
    "%SystemRoot%\System32\curl.exe" -sSfL "https://astral.sh/uv/install.ps1" -o "%TEMP%\install_uv.ps1"
    if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
        "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -ExecutionPolicy Bypass -File "%TEMP%\install_uv.ps1"
    ) else (
        powershell -ExecutionPolicy Bypass -File "%TEMP%\install_uv.ps1"
    )
    del /f /q "%TEMP%\install_uv.ps1" >nul 2>nul
) else (
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -ExecutionPolicy Bypass -Command "iex (irm https://astral.sh/uv/install.ps1)"
)

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    echo uv installed successfully.
    set "UV_RUNNER=uv"
    goto :uv_ready
)
if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
    echo uv installed successfully.
    set "UV_RUNNER=uv"
    goto :uv_ready
)

echo.
echo =======================================================================
echo [ERROR] Could not automatically locate or install uv.
echo.
echo Please run this ONE command in PowerShell to install uv:
echo    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo =======================================================================
pause
exit /b 1

:uv_ready
echo.
echo [2/4] Syncing Python dependencies using uv...
if "%INSTALL_PHISHING%"=="1" (
    echo       Syncing dependencies including PyTorch...
    %UV_RUNNER% sync --extra phishing
    echo.
    echo [3/4] Checking and installing verified phishing model...
    %UV_RUNNER% run --no-sync python -m scripts.install_phishing_model
) else (
    %UV_RUNNER% sync
)

if "%INSTALL_DEMO_DATA%"=="1" (
    echo.
    echo [4/4] Checking and installing sample demo data...
    %UV_RUNNER% run --no-sync python -m scripts.install_demo_data
)

echo.
echo ======================================================
echo   ForeSight is ready!
echo   Open: http://127.0.0.1:%DECISIONIQ_PORT%
echo   Press Ctrl+C in this terminal to stop the server.
echo ======================================================
echo.
%UV_RUNNER% run --no-sync uvicorn decisioniq.main:app --host 127.0.0.1 --port %DECISIONIQ_PORT%
pause
