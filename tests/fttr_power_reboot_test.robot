*** Settings ***
Documentation     FTTR设备断电重启状态自动化测试
...
...               测试流程（对应禅道用例步骤）：
...               步骤1：获取基准dump.txt内容并验证
...               步骤2：继电器断电
...               步骤3：验证设备已掉电
...               步骤4：等待断电保持时间
...               步骤5：继电器上电
...               步骤6：轮询ping等待设备恢复
...               步骤7：telnet到从设备获取dump.txt
...               步骤8：验证dump.txt内容有效、无异常关键词、拓扑正常
...               步骤9：重复步骤2~8共N次

Library           OperatingSystem
Library           libraries.relay_controller.RelayController
Library           libraries.fttr_checker.FttrChecker

*** Variables ***
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
@{ERROR_KEYWORDS}        panic    exception    call_trace    kernel panic


*** Test Cases ***
FTTR设备断电重启循环测试
    [Documentation]    循环断电重启FTTR设备，验证每次重启后设备状态正常
    [Setup]    初始化测试环境
    [Teardown]    清理测试环境

    ${total}=    Set Variable    ${LOOP_COUNT}
    Log    ================================
    Log    开始FTTR断电重启测试，共循环 ${total} 次
    Log    ================================

    FOR    ${round}    IN RANGE    ${total}
        ${round_num}=    Evaluate    ${round} + 1
        Log    \n************************************
        Log    * 第 ${round_num}/${total} 轮测试开始
        Log    ************************************
        ${round_result}=    Run Keyword And Return Status
        ...    执行单轮断电重启测试    ${round_num}    ${total}
        IF    not ${round_result}
            Fail    \n>>>>> 第 ${round_num}/${total} 轮测试失败 <<<<<
        END
        Log    \n==== 第 ${round_num}/${total} 轮测试通过 ====
    END

    Log    \n================================
    Log    全部 ${total} 轮测试通过！FTTR设备断电重启功能正常
    Log    ================================


*** Keywords ***
初始化测试环境
    [Documentation]    连接继电器，确认设备初始状态正常（对应步骤1）
    Log    [步骤1] 初始化测试环境

    # 连接继电器
    Connect Relay    ${RELAY_PORT}    9600
    Log    [步骤1.1] 继电器串口已连接: ${RELAY_PORT} -> PASS

    # 确认设备当前可达
    ${ping_ok}=    Run Keyword And Return Status
    ...    Ping Device Until Online    ${MASTER_IP}    timeout=30    interval=5
    IF    not ${ping_ok}
        Fail    [步骤1.2] 设备初始状态不可达，请确认FTTR设备状态 -> FAIL
    END
    Log    [步骤1.2] 设备初始可达性验证 (${MASTER_IP}) -> PASS

    # 等待主设备telnet服务就绪
    Sleep    10s    等待主设备telnet服务就绪

    # 获取基准dump.txt内容
    ${baseline}=    Get Dump File Content
    ...    ${MASTER_IP}    ${TELNET_USER}    ${TELNET_PASSWORD}
    ...    ${ROOT_PASSWORD}    ${DUMP_FILE}
    Set Dump Baseline    ${baseline}
    ${blen}=    Evaluate    len('''${baseline}''')
    Log    [步骤1.3] 获取基准dump.txt内容 (长度: ${blen}) -> PASS

    # 验证基准内容是有效JSON
    ${devices}=    Parse Topology Info    ${baseline}
    Verify Topology Not Empty    ${devices}
    ${dlen}=    Evaluate    len(${devices})
    Log    [步骤1.4] 基准拓扑信息验证通过，发现 ${dlen} 个设备 -> PASS

清理测试环境
    [Documentation]    确保继电器处于打开状态，断开串口连接
    Run Keyword And Ignore Error    Send Relay On
    Disconnect Relay
    Log    [清理] 继电器已恢复上电状态，串口已断开

执行单轮断电重启测试
    [Documentation]    执行一轮完整的断电-上电-验证流程（对应步骤2~8）
    [Arguments]    ${round_num}    ${total}

    # === 步骤2：断电 ===
    Log    [步骤2] 第${round_num}轮 - 发送继电器断电指令...
    Send Relay Off
    Sleep    2s    等待继电器动作
    Log    [步骤2] 第${round_num}轮 - 继电器断电指令已发送 -> PASS

    # === 步骤3：验证设备已掉电 ===
    Log    [步骤3] 第${round_num}轮 - 验证设备是否已掉电...
    ${offline}=    Wait Until Device Offline    ${MASTER_IP}    timeout=30
    IF    not ${offline}
        Fail    [步骤3] 第${round_num}轮 - 断电后设备仍然在线(${MASTER_IP})，继电器可能未生效 -> FAIL
    END
    Log    [步骤3] 第${round_num}轮 - 设备已确认掉电 (${MASTER_IP}不可达) -> PASS

    # === 步骤4：等待断电保持时间 ===
    Log    [步骤4] 第${round_num}轮 - 断电保持 ${POWER_OFF_DURATION} 秒...
    Sleep    ${POWER_OFF_DURATION}s    断电保持中
    Log    [步骤4] 第${round_num}轮 - 断电保持 ${POWER_OFF_DURATION} 秒完成 -> PASS

    # === 步骤5：上电 ===
    Log    [步骤5] 第${round_num}轮 - 发送继电器上电指令...
    Send Relay On
    Sleep    2s    等待继电器动作
    Log    [步骤5] 第${round_num}轮 - 继电器上电指令已发送 -> PASS

    # === 步骤6：轮询ping等待设备恢复 ===
    Log    [步骤6] 第${round_num}轮 - 等待设备恢复上线 (超时: ${PING_TIMEOUT}s)...
    ${online}=    Ping Device Until Online
    ...    ${MASTER_IP}    timeout=${PING_TIMEOUT}    interval=${PING_INTERVAL}
    IF    not ${online}
        Fail    [步骤6] 第${round_num}轮 - 设备在 ${PING_TIMEOUT} 秒内未恢复上线 -> FAIL
    END
    Log    [步骤6] 第${round_num}轮 - 主设备已恢复在线 (${MASTER_IP}) -> PASS

    # === 步骤7：telnet到从设备获取dump.txt ===
    Log    [步骤7] 第${round_num}轮 - telnet到从设备获取dump.txt...
    Sleep    10s    额外等待从设备完全启动
    ${current_content}=    Get Dump File Content
    ...    ${MASTER_IP}    ${TELNET_USER}    ${TELNET_PASSWORD}
    ...    ${ROOT_PASSWORD}    ${DUMP_FILE}
    Set Dump Current    ${current_content}
    Log    [步骤7] 第${round_num}轮 - dump.txt内容获取成功 -> PASS

    # === 步骤8：验证dump.txt内容 ===
    Log    [步骤8] 第${round_num}轮 - 验证dump.txt内容...

    # 8.1 验证内容有效
    Check Dump Content Valid
    Log    [步骤8.1] 第${round_num}轮 - dump.txt JSON格式有效且包含topology information -> PASS

    # 8.2 验证无异常关键词
    Check Dump No Error Keywords    ${ERROR_KEYWORDS}
    Log    [步骤8.2] 第${round_num}轮 - dump.txt未发现异常关键词 -> PASS

    # 8.3 验证拓扑信息有效
    ${devices}=    Parse Topology Info    ${current_content}
    Verify Topology Not Empty    ${devices}
    ${dlen}=    Evaluate    len(${devices})
    Log    [步骤8.3] 第${round_num}轮 - 拓扑信息有效，${dlen} 个设备 -> PASS

    Log    [步骤8] 第${round_num}轮 - dump.txt全部验证通过 -> PASS

    # 更新基准为当前内容
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
