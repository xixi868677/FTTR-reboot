@echo off
chcp 65001 >nul 2>&1

REM ==============================================
REM   FTTR Power Reboot Test - Run + Sync Zentao
REM   Usage: run_and_sync.bat <Zentao Case ID> [Task ID]
REM   Example: run_and_sync.bat 853
REM   Example: run_and_sync.bat 853 12
REM ==============================================

setlocal EnableDelayedExpansion

set CASE_ID=%1
set TASK_ID=%2
if "%CASE_ID%"=="" (
    echo [ERROR] Please provide Zentao case ID
    echo Usage: run_and_sync.bat ^<CaseID^> [TaskID]
    echo Example: run_and_sync.bat 853
    echo Example: run_and_sync.bat 853 12
    exit /b 1
)

REM ====== Config Area ======
set ZENTAO_URL=https://zt.hzbox.net
set ZENTAO_USER=xuwenjun
set ZENTAO_PWD=cncr@_3UjxEX9h1A
REM ====== Config End ======

echo ========================================
echo   FTTR Power Reboot Auto Test
echo   Zentao Case ID: %CASE_ID%
if not "%TASK_ID%"=="" echo   Zentao Task ID: %TASK_ID%
echo ========================================
echo.

REM Step 1: Run Robot Framework Test
echo [Step 1] Running Robot Framework test...

set CONFIG_FILE=config.local.yaml
if not exist config.local.yaml set CONFIG_FILE=config.yaml
echo [INFO] Config file: %CONFIG_FILE%

python -m robot --outputdir results --timestampoutputs ^
    --pythonpath . ^
    --variablefile %CONFIG_FILE% ^
    --logtitle "FTTR Power Reboot Test Log" ^
    --reporttitle "FTTR Power Reboot Test Report" ^
    tests/fttr_power_reboot_test.robot

set TEST_RC=%errorlevel%
echo.
echo [INFO] Test done, return code: %TEST_RC%

REM Step 2: Find latest output.xml
for /f "delims=" %%i in ('dir /b /o-d results\output*.xml 2^>nul') do (
    set OUTPUT_XML=results\%%i
    goto :found_xml
)
echo [ERROR] output.xml not found
exit /b 1

:found_xml
echo [INFO] Result file: %OUTPUT_XML%
echo.

REM Step 3: Sync result to Zentao
echo [Step 2] Syncing result to Zentao...
if "%TASK_ID%"=="" (
    python libraries\zentao_sync.py ^
        --xml %OUTPUT_XML% ^
        --url %ZENTAO_URL% ^
        --user %ZENTAO_USER% ^
        --pwd %ZENTAO_PWD% ^
        --case-id %CASE_ID%
) else (
    python libraries\zentao_sync.py ^
        --xml %OUTPUT_XML% ^
        --url %ZENTAO_URL% ^
        --user %ZENTAO_USER% ^
        --pwd %ZENTAO_PWD% ^
        --case-id %CASE_ID% ^
        --task-id %TASK_ID%
)

echo.
echo ========================================
echo   Done!
echo   Result: %OUTPUT_XML%
echo   Zentao Case: %CASE_ID%
echo ========================================
pause
