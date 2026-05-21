*** Settings ***
Documentation     FTTR设备断电重启状态自动化测试
...
...               测试流程：
...               1. 获取基准dump.txt内容
...               2. 继电器断电 -> 验证掉电 -> 等待 -> 上电
...               3. 轮询ping等待设备恢复
...               4. telnet到从设备检查dump.txt
...               5. 验证内容更新且无异常关键词
...               6. 循环N次

Library           OperatingSystem
Library           libraries.relay_controller.RelayController
Library           libraries.fttr_checker.FttrChecker

# 优先加载本地配置（含真实密码），不存在则加载模板
Library           OperatingSystem
# Variables会在Settings阶段加载，用条件判断不方便
# 约定：本地运行时在命令行用 --variablefile config.local.yaml 覆盖
# Jenkins上也通过 --variablefile 传入真实配置

*** Variables ***
# 这些变量会被config.yaml中的值覆盖
# 如果不用yaml，也可以直接在这里改
${RELAY_PORT}         COM3
${MASTER_IP}          192.168.1.1
${SLAVE_IP}           192.168.1.2
${TELNET_USER}        admin
${TELNET_PASSWORD}    admin@123
${ROOT_PASSWORD}      aDm8H%MdA
${DUMP_FILE}          /tmp/dump.txt
${POWER_OFF_DURATION}    10
${PING_INTERVAL}         10
${PING_TIMEOUT}          180
${LOOP_COUNT}            5
@{ERROR_KEYWORDS}        panic    error    exception    fault    fail


*** Test Cases ***
FTTR设备断电重启循环测试
    [Documentation]    循环断电重启FTTR设备，验证每次重启后设备状态正常
    [Setup]    初始化测试环境
    [Teardown]    清理测试环境

    # 记录循环计数
    ${total}=    Set Variable    ${LOOP_COUNT}
    Log    开始FTTR断电重启测试，共循环 ${total} 次

    FOR    ${round}    IN RANGE    ${total}
        Log    ========== 第 ${round+1}/${total} 轮测试开始 ==========
        ${round_result}=    执行单轮断电重启测试    ${round+1}
        Run Keyword If    '${round_result}' == 'FAIL'
        ...    Fail    第 ${round+1} 轮测试失败
        Log    ========== 第 ${round+1}/${total} 轮测试通过 ==========
    END

    Log    全部 ${total} 轮测试通过！FTTR设备断电重启功能正常


*** Keywords ***
初始化测试环境
    [Documentation]    连接继电器，确认设备初始状态正常
    # 连接继电器
    Connect Relay    ${RELAY_PORT}    9600
    Log    继电器串口已连接: ${RELAY_PORT}

    # 确认设备当前可达
    ${ping_ok}=    Run Keyword And Return Status
    ...    Ping Device Until Online    ${MASTER_IP}    timeout=30    interval=5
    IF    not ${ping_ok}
        Fail    初始化失败：设备当前不可达，请确认FTTR设备状态
    END

    # 获取基准dump.txt内容
    ${baseline}=    Get Dump File Content
    ...    ${SLAVE_IP}    ${TELNET_USER}    ${TELNET_PASSWORD}
    ...    ${ROOT_PASSWORD}    ${DUMP_FILE}
    Set Dump Baseline    ${baseline}
    Log    已获取dump.txt基准内容（长度: ${baseline.__len__()}）

    # 验证基准内容是有效JSON
    ${devices}=    Parse Topology Info    ${baseline}
    Verify Topology Not Empty    ${devices}
    Log    基准拓扑信息有效，发现 ${devices.__len__()} 个设备

清理测试环境
    [Documentation]    确保继电器处于打开状态，断开串口连接
    Run Keyword And Ignore Error    Send Relay On
    Disconnect Relay
    Log    测试环境已清理，继电器已断开

执行单轮断电重启测试
    [Documentation]    执行一轮完整的断电-上电-验证流程
    [Arguments]    ${round_num}

    # Step 1: 断电
    Log    [Round ${round_num}] 发送断电指令...
    Send Relay Off
    Sleep    2s    等待继电器动作

    # Step 2: 验证设备已断电（ping不通）
    ${offline}=    Run Keyword And Return Status
    ...    Wait Until Device Offline    ${MASTER_IP}    timeout=30
    IF    not ${offline}
        Fail    [Round ${round_num}] 断电后设备仍然在线，继电器可能未生效
    END
    Log    [Round ${round_num}] 设备已确认断电

    # Step 3: 等待断电保持时间
    Sleep    ${POWER_OFF_DURATION}s    断电保持中，等待 ${POWER_OFF_DURATION} 秒

    # Step 4: 上电
    Log    [Round ${round_num}] 发送上电指令...
    Send Relay On
    Sleep    2s    等待继电器动作

    # Step 5: 轮询ping等待设备恢复
    ${online}=    Ping Device Until Online
    ...    ${MASTER_IP}    timeout=${PING_TIMEOUT}    interval=${PING_INTERVAL}
    IF    not ${online}
        Fail    [Round ${round_num}] 设备在 ${PING_TIMEOUT} 秒内未能恢复上线
    END
    Log    [Round ${round_num}] 主设备已恢复在线

    # Step 6: telnet到从设备获取dump.txt
    Sleep    10s    额外等待从设备完全启动
    ${current_content}=    Get Dump File Content
    ...    ${SLAVE_IP}    ${TELNET_USER}    ${TELNET_PASSWORD}
    ...    ${ROOT_PASSWORD}    ${DUMP_FILE}
    Set Dump Current    ${current_content}
    Log    [Round ${round_num}] 已获取当前dump.txt内容

    # Step 7: 验证内容更新
    Check Dump Content Updated
    Log    [Round ${round_num}] dump.txt内容已更新

    # Step 8: 验证无异常关键词
    Check Dump No Error Keywords    ${ERROR_KEYWORDS}
    Log    [Round ${round_num}] dump.txt未发现异常关键词

    # Step 9: 验证拓扑信息有效
    ${devices}=    Parse Topology Info    ${current_content}
    Verify Topology Not Empty    ${devices}
    Log    [Round ${round_num}] 拓扑信息有效，${devices.__len__()} 个设备

    # 更新基准为当前内容，供下一轮比较
    Set Dump Baseline    ${current_content}

Ping Device Until Online
    [Documentation]    轮询ping设备直到上线或超时
    [Arguments]    ${ip}    ${timeout}=180    ${interval}=10
    ${start_time}=    Get Time    epoch
    ${deadline}=    Evaluate    ${start_time} + ${timeout}
    ${reached}=    Set Variable    ${FALSE}
    FOR    ${i}    IN RANGE    999
        ${now}=    Get Time    epoch
        ${remaining}=    Evaluate    ${deadline} - ${now}
        IF    ${remaining} <= 0
            BREAK
        END
        ${result}=    Run And Return Rc    ping -n 1 -w 3000 ${ip}
        ${reached}=    Set Variable If    ${result} == 0    ${TRUE}    ${FALSE}
        IF    ${reached}
            BREAK
        END
        Sleep    ${interval}s    Ping未通，${interval}秒后重试...
    END
    RETURN    ${reached}

Wait Until Device Offline
    [Documentation]    等待设备离线（ping不通）
    [Arguments]    ${ip}    ${timeout}=30
    ${start_time}=    Get Time    epoch
    ${deadline}=    Evaluate    ${start_time} + ${timeout}
    FOR    ${i}    IN RANGE    10
        ${result}=    Run And Return Rc    ping -n 1 -w 3000 ${ip}
        IF    ${result} != 0
            BREAK
        END
        ${now}=    Get Time    epoch
        ${remaining}=    Evaluate    ${deadline} - ${now}
        IF    ${remaining} <= 0
            BREAK
        END
        Sleep    3s    设备仍在线，3秒后重试...
    END
    ${result}=    Run And Return Rc    ping -n 1 -w 3000 ${ip}
    RETURN    ${result} != 0
