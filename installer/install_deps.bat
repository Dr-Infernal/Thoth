@echo off
:: ============================================================================
:: Post-install script – sets up embedded Python environment
:: Called by Inno Setup after file extraction
:: ============================================================================
set "INSTALL_DIR=%~1"
set "PYTHON_DIR=%INSTALL_DIR%\python"
set "PYTHON=%PYTHON_DIR%\python.exe"
set "APP_DIR=%INSTALL_DIR%\app"

echo =========================================
echo  Thoth – Installing Python packages...
echo =========================================
echo.

:: ── Enable pip in embedded Python ───────────────────────────────────────────
:: The embedded distribution ships with a ._pth file that restricts imports.
:: We need to uncomment "import site" so pip/setuptools work.
for %%f in ("%PYTHON_DIR%\python*._pth") do (
    echo Patching %%f to enable pip...
    powershell -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
)

:: ── Install pip ─────────────────────────────────────────────────────────────
echo Installing pip...
"%PYTHON%" "%INSTALL_DIR%\get-pip.py" --no-warn-script-location
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install pip.
    exit /b 1
)

:: ── Install requirements ────────────────────────────────────────────────────
echo.
echo Installing Python packages (this may take several minutes)...
"%PYTHON%" -m pip install --no-warn-script-location -r "%APP_DIR%\requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install some packages.
    exit /b 1
)

echo.
echo =========================================
echo  Python packages installed successfully!
echo =========================================
exit /b 0
