@echo off
chcp 65001 >nul 2>&1

REM FTTR Power Reboot Auto Test - Run Script
REM Usage: run_test.bat or double-click to run

echo ========================================
echo   FTTR Power Reboot Auto Test
echo ========================================
echo.

REM Check python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.10+
    pause
    exit /b 1
)

REM Check robotframework
python -c "import robot" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install robotframework pyserial paramiko pyyaml
)

echo [INFO] Running test...
echo.

REM Pick config file
set CONFIG_FILE=config.local.yaml
if not exist config.local.yaml set CONFIG_FILE=config.yaml
echo [INFO] Config file: %CONFIG_FILE%

REM Run Robot Framework test
python -m robot --outputdir results --timestampoutputs ^
    --pythonpath . ^
    --variablefile %CONFIG_FILE% ^
    --logtitle "FTTR Power Reboot Test Log" ^
    --reporttitle "FTTR Power Reboot Test Report" ^
    tests/fttr_power_reboot_test.robot

echo.
echo ========================================
echo   Test Done! Results in results/ folder
echo   - output.xml  (for Jenkins Robot plugin)
echo   - log.html    (detail log)
echo   - report.html (test report)
echo ========================================
pause
