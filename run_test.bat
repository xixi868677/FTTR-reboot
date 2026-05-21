@echo off
REM FTTR断电重启自动化测试启动脚本
REM 用法: run_test.bat 或双击运行

echo ========================================
echo   FTTR断电重启自动化测试
echo ========================================
echo.

REM 检查python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

REM 检查robotframework
python -c "import robot" >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装robotframework，正在安装...
    pip install robotframework pyserial paramiko pyyaml
)

echo [信息] 开始执行测试...
echo.

REM 判断使用哪个配置文件
set CONFIG_FILE=config.local.yaml
if not exist config.local.yaml set CONFIG_FILE=config.yaml
echo [信息] 使用配置文件: %CONFIG_FILE%

REM 执行Robot Framework测试
python -m robot --outputdir results --timestampoutputs ^
    --pythonpath . ^
    --variablefile %CONFIG_FILE% ^
    --logtitle "FTTR断电重启测试日志" ^
    --reporttitle "FTTR断电重启测试报告" ^
    tests/fttr_power_reboot_test.robot

echo.
echo ========================================
echo   测试完成！结果在 results/ 目录下
echo   - output.xml  (Jenkins Robot插件解析)
echo   - log.html    (详细日志)
echo   - report.html (测试报告)
echo ========================================
pause
