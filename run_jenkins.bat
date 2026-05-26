@echo off
chcp 65001 >nul 2>&1

REM FTTR Power Reboot Test - For Jenkins (no pause)
REM Usage: run_jenkins.bat <Zentao Case ID>
REM Example: run_jenkins.bat 853

setlocal EnableDelayedExpansion

set CASE_ID=%1

REM Pick config file
set CONFIG_FILE=config.local.yaml
if not exist config.local.yaml set CONFIG_FILE=config.yaml

echo ========================================
echo   FTTR Power Reboot Auto Test
if not "%CASE_ID%"=="" echo   Zentao Case ID: %CASE_ID%
echo ========================================
echo.

REM Step 1: Run Robot Framework test
echo [Step 1] Running Robot Framework test...

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

REM Step 3: Sync to Zentao (if case ID provided)
if "%CASE_ID%"=="" goto :skip_zentao

echo [Step 2] Syncing result to Zentao...
if not defined ZENTAO_PWD (
    set ZENTAO_PWD=cncr@_3UjxEX9h1A
)
if not defined ZENTAO_URL (
    set ZENTAO_URL=https://zt.hzbox.net
)
if not defined ZENTAO_USER (
    set ZENTAO_USER=xuwenjun
)

python libraries\zentao_sync.py ^
    --xml %OUTPUT_XML% ^
    --url %ZENTAO_URL% ^
    --user %ZENTAO_USER% ^
    --pwd %ZENTAO_PWD% ^
    --case-id %CASE_ID%

echo.

:skip_zentao

REM Step 4: Send result to WeChat Work group
echo [Step 3] Sending result to WeChat Work group...
python libraries\wechat_notify.py --xml %OUTPUT_XML%

echo.
echo ========================================
echo   Done!
echo   Result: %OUTPUT_XML%
if not "%CASE_ID%"=="" echo   Zentao Case: %CASE_ID%
echo ========================================

exit /b %TEST_RC%
