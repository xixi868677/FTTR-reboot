"""FTTR设备检查库 - telnet登录、dump.txt内容检查"""

import json
import telnetlib
import time


class FttrChecker:
    """Robot Framework库：FTTR设备状态检查"""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._dump_baseline = ""
        self._dump_current = ""

    def get_dump_file_content(self, host, user, password, root_password, dump_file="/tmp/dump.txt"):
        """Telnet到设备获取dump.txt内容

        登录流程: telnet -> admin -> su root -> mapd_cli触发 -> cat dump.txt
        连接失败或文件不存在时自动重试，最多10次，每次间隔15秒。
        """
        last_error = ""
        for attempt in range(10):
            try:
                content = self._telnet_get_dump(host, user, password, root_password, dump_file)
                if content and "No such file" not in content and "cannot open" not in content:
                    return content
                last_error = content[:200] if content else "empty"
                if attempt < 9:
                    print(f"[Retry] dump.txt not ready, waiting 15s... (attempt {attempt+1}/10)")
                    time.sleep(15)
            except (TimeoutError, OSError) as e:
                last_error = str(e)
                if attempt < 9:
                    print(f"[Retry] telnet failed, waiting 15s... (attempt {attempt+1}/10)")
                    time.sleep(15)
                    continue
        raise RuntimeError(
            f"Failed to get {dump_file} from {host} after 10 attempts. Last: {last_error}"
        )

    def _telnet_get_dump(self, host, user, password, root_password, dump_file):
        """单次telnet连接：登录 -> su root -> 触发生成 -> cat读取"""
        tn = telnetlib.Telnet(host, timeout=30)

        # 登录
        tn.read_until(b"ogin:", timeout=10)
        tn.write(user.encode() + b"\n")
        tn.read_until(b"assword:", timeout=10)
        tn.write(password.encode() + b"\n")
        time.sleep(1)
        tn.read_until(b"$", timeout=10)

        # su root
        tn.write(b"su root\n")
        time.sleep(2)
        su_output = tn.read_very_eager().decode("utf-8", errors="ignore")
        if "assword" in su_output:
            tn.write(root_password.encode() + b"\n")
            time.sleep(2)
            tn.read_very_eager()

        # 触发dump.txt生成
        tn.write(b"mapd_cli /tmp/mapd_ctrl dump_topology_v1\n")
        time.sleep(3)
        tn.read_until(b"$", timeout=15)

        # 清空缓冲区
        time.sleep(1)
        try:
            tn.read_very_eager()
        except Exception:
            pass

        # 读取dump.txt内容
        tn.write(f"cat {dump_file}\n".encode())
        time.sleep(3)
        output = tn.read_until(b"$", timeout=15).decode("utf-8", errors="ignore")

        # 提取cat命令之后、下一个提示符之前的内容
        lines = output.split("\n")
        content_lines = []
        started = False
        for line in lines:
            if f"cat {dump_file}" in line:
                started = True
                continue
            if started and line.strip().endswith("$"):
                break
            if started:
                content_lines.append(line)

        content = "\n".join(content_lines).strip()

        # 关闭连接
        tn.write(b"exit\n")
        tn.write(b"exit\n")
        tn.close()

        return content

    def set_dump_baseline(self, content):
        """保存dump.txt内容作为基准"""
        self._dump_baseline = content

    def set_dump_current(self, content):
        """保存当前的dump.txt内容"""
        self._dump_current = content

    def check_dump_content_valid(self):
        """检查dump.txt内容是否有效（非空、可解析为JSON、包含拓扑信息）"""
        if not self._dump_current or not self._dump_current.strip():
            raise AssertionError("dump.txt内容为空，设备可能未正常启动")
        try:
            data = json.loads(self._dump_current)
        except json.JSONDecodeError:
            raise AssertionError(f"dump.txt不是有效JSON: {self._dump_current[:200]}")
        topology = data.get("topology information")
        if topology is None:
            raise AssertionError("dump.txt中未找到topology information字段")
        return True

    def check_dump_no_error_keywords(self, error_keywords):
        """检查dump.txt内容中是否包含异常关键词"""
        content_lower = self._dump_current.lower()
        found_errors = []
        for keyword in error_keywords:
            if keyword.lower() in content_lower:
                found_errors.append(keyword)
        if found_errors:
            raise AssertionError(
                f"dump.txt中发现异常关键词: {found_errors}"
            )
        return True

    def parse_topology_info(self, content):
        """解析dump.txt中的topology information，返回设备列表"""
        try:
            data = json.loads(content)
            topology = data.get("topology information", [])
            devices = []
            for dev in topology:
                devices.append({
                    "al_mac": dev.get("AL MAC", "unknown"),
                    "role": dev.get("Device role", "unknown"),
                    "distance": dev.get("Distance from controller", "unknown"),
                })
            return devices
        except json.JSONDecodeError:
            raise AssertionError(f"dump.txt内容不是有效JSON，无法解析: {content[:200]}")

    def verify_topology_not_empty(self, devices):
        """验证拓扑信息不为空"""
        if not devices:
            raise AssertionError("拓扑信息为空，设备状态异常")
        return True
