"""FTTR设备检查库 - telnet登录、dump.txt内容检查"""

import base64
import json
import re
import telnetlib
import time

import requests


class FttrChecker:
    """Robot Framework库：FTTR设备状态检查"""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._dump_baseline = ""
        self._dump_current = ""
        self._http_session = requests.Session()
        self._web_logged_in_host = ""

    @staticmethod
    def _encrypt_password(password):
        """AES-128-CBC加密（与设备管理平台JS加密一致）"""
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        key = b"1111111111111111"
        iv = b"0000000000000000"
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(password.encode("utf-8"), AES.block_size, style="pkcs7")
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode("utf-8")

    def _web_login(self, host, web_user, web_pwd):
        """登录设备Web管理平台"""
        login_url = f"http://{host}/"
        try:
            page = self._http_session.get(login_url, timeout=10)
            token_match = re.search(r'Frm_Logintoken.*?value="(\d+)"', page.text)
            token = token_match.group(1) if token_match else "2"
        except Exception:
            token = "2"

        logincode = self._encrypt_password(web_pwd)
        payload = {
            "action": "login",
            "Frm_Logintoken": token,
            "username": web_user,
            "logincode": logincode,
            "textpwd": "",
            "ieversion": "1",
        }
        resp = self._http_session.post(login_url, data=payload, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            self._web_logged_in_host = host
            print(f"[Dump] Web登录成功: {host}")
        else:
            print(f"[Dump] Web登录失败: {resp.status_code}")

    def trigger_dump_generation(self, host, web_user="CMCCAdmin", web_pwd=""):
        """登录管理平台并访问拓扑页面，触发dump.txt生成"""
        if not web_pwd:
            print("[Dump] 无web密码，跳过触发")
            return
        if self._web_logged_in_host != host:
            try:
                self._web_login(host, web_user, web_pwd)
            except Exception as e:
                print(f"[Dump] Web登录异常: {e}")
                return
        # 先加载外层页面，再加载iframe内容（iframe才是真正触发生成的）
        base_url = f"http://{host}/getpage.gch?pid=1002&nextpage=app_easymesh_topo_t.gch"
        iframe_url = f"http://{host}/template.gch?pid=1002&nextpage=app_easymesh_topo_t.gch"
        try:
            self._http_session.get(base_url, timeout=10)
            resp = self._http_session.get(iframe_url, timeout=10)
            if resp.status_code == 200:
                print(f"[Dump] 已触发dump.txt生成")
            else:
                print(f"[Dump] iframe返回非200: {resp.status_code}")
        except requests.RequestException as e:
            print(f"[Dump] 触发请求失败: {e}")

    def get_dump_file_content(self, host, user, password, root_password, dump_file="/tmp/dump.txt"):
        """Telnet到设备获取dump.txt内容

        登录流程: telnet -> admin/admin@123 -> su root -> cat dump.txt
        连接失败或文件不存在时自动重试，最多5次，每次间隔15秒。
        """
        last_error = ""
        for attempt in range(10):
            try:
                # 先触发dump.txt生成
                self.trigger_dump_generation(host, web_pwd=root_password)
                time.sleep(3)

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
        """单次telnet连接获取dump.txt内容"""
        tn = telnetlib.Telnet(host, timeout=30)

        # 等待Login提示（匹配ogin:兼容大小写）
        tn.read_until(b"ogin:", timeout=10)
        tn.write(user.encode() + b"\n")

        # 等待Password提示
        tn.read_until(b"assword:", timeout=10)
        tn.write(password.encode() + b"\n")

        # 等待shell提示符 $
        tn.read_until(b"$", timeout=10)

        # su root
        tn.write(b"su root\n")
        tn.read_until(b"assword:", timeout=10)
        tn.write(root_password.encode() + b"\n")
        time.sleep(1)
        tn.read_until(b"$", timeout=10)

        # 执行cat dump文件
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
