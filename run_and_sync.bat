@echo off
REM ==============================================
REM   FTTR断电重启测试 - 本地一键运行+同步Jenkins
REM   用法: run_and_sync.bat <禅道用例ID>
REM   示例: run_and_sync.bat 123
REM   示例: run_and_sync.bat 123,124,125
REM ==============================================

setlocal EnableDelayedExpansion

set CASE_ID=%1
if "%CASE_ID%"=="" (
    echo [错误] 请提供禅道用例ID
    echo 用法: run_and_sync.bat ^<禅道用例ID^>
    echo 示例: run_and_sync.bat 123
    exit /b 1
)

REM ====== 配置区域（按需修改）======
set JENKINS_URL=http://你的Jenkins地址
set JENKINS_JOB=FTTR-reboot-sync
set JENKINS_USER=你的Jenkins用户名
set JENKINS_TOKEN=你的Jenkins API Token
set ZENTAO_PWD=cncr@_3UjxEX9h1A
REM ====== 配置区域结束 ======

echo ========================================
echo   FTTR断电重启自动化测试
echo   禅道用例ID: %CASE_ID%
echo ========================================
echo.

REM Step 1: 运行Robot Framework测试
echo [Step 1] 执行Robot Framework测试...

set CONFIG_FILE=config.local.yaml
if not exist config.local.yaml set CONFIG_FILE=config.yaml
echo [信息] 使用配置文件: %CONFIG_FILE%

python -m robot --outputdir results --timestampoutputs ^
    --pythonpath . ^
    --variablefile %CONFIG_FILE% ^
    --logtitle "FTTR断电重启测试日志" ^
    --reporttitle "FTTR断电重启测试报告" ^
    tests/fttr_power_reboot_test.robot

set TEST_RC=%errorlevel%
echo.
echo [信息] 测试执行完毕，返回码: %TEST_RC%

REM Step 2: 找到最新的output.xml
for /f "delims=" %%i in ('dir /b /o-d results\output*.xml 2^>nul') do (
    set OUTPUT_XML=results\%%i
    goto :found_xml
)
echo [错误] 未找到output.xml文件
exit /b 1

:found_xml
echo [信息] 结果文件: %OUTPUT_XML%
echo.

REM Step 3: 直接调用禅道同步脚本（不经过Jenkins也行）
echo [Step 2] 同步测试结果到禅道...
python libraries\zentao_sync.py ^
    --xml %OUTPUT_XML% ^
    --url https://zt.hzbox.net ^
    --user xuwenjun ^
    --pwd %ZENTAO_PWD% ^
    --case-id %CASE_ID%

echo.
echo ========================================
echo   全部完成！
echo   测试结果: %OUTPUT_XML%
echo   禅道用例: %CASE_ID%
echo ========================================
pause
