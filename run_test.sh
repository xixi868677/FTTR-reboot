#!/bin/bash
# FTTR断电重启自动化测试启动脚本 (Linux/Mac)
# 用法: bash run_test.sh

set -e

echo "========================================"
echo "  FTTR断电重启自动化测试"
echo "========================================"
echo

# 检查python3
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到python3"
    exit 1
fi

# 检查依赖
python3 -c "import robot" 2>/dev/null || {
    echo "[信息] 安装依赖..."
    pip3 install robotframework pyserial paramiko pyyaml
}

echo "[信息] 开始执行测试..."
echo

# 选择配置文件
if [ -f config.local.yaml ]; then
    CONFIG_FILE="config.local.yaml"
else
    CONFIG_FILE="config.yaml"
fi
echo "[信息] 使用配置文件: ${CONFIG_FILE}"

# 执行Robot Framework测试
python3 -m robot --outputdir results --timestampoutputs \
    --pythonpath . \
    --variablefile "${CONFIG_FILE}" \
    --logtitle "FTTR断电重启测试日志" \
    --reporttitle "FTTR断电重启测试报告" \
    tests/fttr_power_reboot_test.robot

echo
echo "========================================"
echo "  测试完成！结果在 results/ 目录下"
echo "========================================"
