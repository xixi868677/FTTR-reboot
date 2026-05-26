"""
禅道同步脚本 - 解析Robot Framework output.xml并同步测试结果到禅道

用法:
    python zentao_sync.py --xml output.xml --url https://zt.hzbox.net --user xuwenjun --pwd xxx --case-id 123

也可以通过命令行参数或环境变量配置
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET

import requests


class ZentaoSync:
    """禅道API同步器"""

    def __init__(self, base_url, user, password):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.session = requests.Session()
        self.token = None

    def login(self):
        """登录禅道获取Token"""
        url = f"{self.base_url}/api.php/v1/tokens"
        resp = self.session.post(url, json={
            "account": self.user,
            "password": self.password,
        })
        if resp.status_code in (200, 201):
            data = resp.json()
            self.token = data.get("token")
            if self.token:
                self.session.headers.update({"Token": self.token})
                print(f"[Zentao] Login OK, token: {self.token[:20]}...")
            else:
                raise RuntimeError(f"Zentao login returned no token: {resp.text}")
        else:
            raise RuntimeError(f"Zentao login failed: {resp.status_code} {resp.text}")

    def get_case_steps(self, case_id):
        """获取禅道用例的步骤列表"""
        url = f"{self.base_url}/api.php/v1/testcases/{case_id}"
        resp = self.session.get(url)
        if resp.status_code != 200:
            return []
        case = resp.json()
        return case.get("steps", [])

    def update_test_result(self, case_id, result, step_results=None, fail_msg=""):
        """更新测试用例执行结果

        Args:
            case_id: 禅道用例ID
            result: 'pass' 或 'fail'（整体结果）
            step_results: dict {步骤号: {"result": "pass"/"fail", "real": "描述"}}
            fail_msg: 失败原因
        """
        steps = self.get_case_steps(case_id)
        if not steps:
            print(f"[Zentao] 用例 {case_id} 无步骤信息，尝试直接提交...")
            return self._submit_simple(case_id, result)

        # 找到最后一个有结果的步骤号
        last_executed = 0
        if step_results:
            for k in step_results:
                try:
                    num = int(k)
                    if num > last_executed:
                        last_executed = num
                except ValueError:
                    pass

        # 如果测试失败，最后执行的步骤就是出问题的步骤
        fail_step = last_executed if result == "fail" else 0

        steps_payload = []
        for step in steps:
            step_id = step["id"]
            step_name = step.get("name", "")
            step_num = 0
            try:
                step_num = int(step_name)
            except ValueError:
                pass

            if step_results and step_name in step_results:
                info = step_results[step_name]
                step_result = info["result"]
                step_real = info["real"]

                # 如果这个步骤有PASS日志但它是失败的步骤，标记为fail
                if step_num == fail_step and step_result == "pass":
                    step_result = "fail"
                    step_real = fail_msg if fail_msg else "执行失败"

            elif step_num == fail_step and step_num > last_executed:
                # 失败的步骤（没有日志，推断出来的）
                step_result = "fail"
                step_real = "执行失败"
            elif step_num > fail_step and result == "fail":
                # 失败步骤之后的步骤
                step_result = "blocked"
                step_real = "未执行（前序步骤失败）"
            elif result == "pass":
                step_result = "pass"
                step_real = "pass"
            else:
                step_result = result
                step_real = result

            steps_payload.append({
                "id": step_id,
                "result": step_result,
                "real": step_real,
            })

        # 提交到 /api.php/v1/testcases/{id}/results
        url = f"{self.base_url}/api.php/v1/testcases/{case_id}/results"
        payload = {
            "result": result,
            "steps": steps_payload,
        }

        resp = self.session.post(url, json=payload)
        if resp.status_code in (200, 201):
            print(f"[Zentao] 用例 {case_id} 结果已同步: {result}")
            return True
        else:
            print(f"[Zentao] 提交失败: {resp.status_code} {resp.text[:300]}")
            return False

    def _submit_simple(self, case_id, result):
        """无步骤时简单提交"""
        url = f"{self.base_url}/api.php/v1/testcases/{case_id}/results"
        payload = {"result": result}
        resp = self.session.post(url, json=payload)
        if resp.status_code in (200, 201):
            print(f"[Zentao] 用例 {case_id} 结果已同步(simple): {result}")
            return True
        print(f"[Zentao] simple提交失败: {resp.status_code} {resp.text[:300]}")
        return False


def parse_robot_output(xml_path):
    """解析Robot Framework output.xml

    Returns:
        list of dict: [{'name': ..., 'status': 'PASS'|'FAIL', 'message': ..., 'elapsed': ...,
                        'log_messages': [...]}]
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    results = []

    for test in root.iter("test"):
        name = test.get("name", "unknown")
        status_elem = test.find("status")
        status = status_elem.get("status", "UNKNOWN") if status_elem is not None else "UNKNOWN"
        message = status_elem.text.strip() if status_elem is not None and status_elem.text else ""
        elapsed = status_elem.get("elapsed", "0") if status_elem is not None else "0"

        log_messages = _collect_keyword_logs(test)

        results.append({
            "name": name,
            "status": status,
            "message": message,
            "elapsed": elapsed,
            "log_messages": log_messages,
        })

    if not results:
        print(f"[警告] output.xml中未找到测试用例: {xml_path}")

    return results


def _collect_keyword_logs(element):
    """递归收集keyword中的log消息"""
    messages = []
    for kw in element.findall("kw"):
        child_msgs = _collect_keyword_logs(kw)
        messages.extend(child_msgs)

        for msg in kw.findall("msg"):
            level = msg.get("level", "INFO")
            text = msg.text.strip() if msg.text else ""
            if text and level in ("INFO", "WARN", "FAIL"):
                messages.append(text)

    return messages


def build_step_results(test_results):
    """从Robot Framework日志中构建禅道步骤结果映射

    返回 dict: {步骤号: {"result": "pass"/"fail", "real": "描述"}}
    """
    step_map = {}
    for r in test_results:
        for msg in r.get("log_messages", []):
            if "[步骤" in msg and "] " in msg:
                start = msg.index("[步骤") + 4
                end = msg.index("]", start)
                step_num = msg[start:end].split(".")[0]
                if " -> PASS" in msg:
                    step_map[step_num] = {
                        "result": "pass",
                        "real": msg.replace(" -> PASS", " ✅").strip(),
                    }
                elif " -> FAIL" in msg:
                    step_map[step_num] = {
                        "result": "fail",
                        "real": msg.replace(" -> FAIL", " ❌").strip(),
                    }
                else:
                    step_map[step_num] = {
                        "result": "pass",
                        "real": msg.strip(),
                    }
    return step_map


def build_steps_info(test_results):
    """将测试结果格式化为步骤信息字符串"""
    lines = []
    for r in test_results:
        lines.append(f"测试用例: {r['name']} - {r['status']}")
        if r["message"]:
            lines.append(f"  失败原因: {r['message']}")
        lines.append(f"  耗时: {r.get('elapsed', 'N/A')}秒")
        lines.append("  --- 详细步骤 ---")

        for msg in r.get("log_messages", []):
            if "[步骤" in msg or "轮测试" in msg or "PASS" in msg or "FAIL" in msg:
                lines.append(f"  {msg}")

        lines.append("  --- 步骤结束 ---")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="解析output.xml并同步禅道")
    parser.add_argument("--xml", required=True, help="Robot Framework output.xml路径")
    parser.add_argument("--url", default=os.getenv("ZENTAO_URL", "https://zt.hzbox.net"),
                        help="禅道地址")
    parser.add_argument("--user", default=os.getenv("ZENTAO_USER", "xuwenjun"),
                        help="禅道用户名")
    parser.add_argument("--pwd", default=os.getenv("ZENTAO_PWD", ""),
                        help="禅道密码")
    parser.add_argument("--case-id", required=True,
                        help="禅道用例ID（多个用逗号分隔）")
    args = parser.parse_args()

    if not args.pwd:
        print("[错误] 请通过 --pwd 参数或 ZENTAO_PWD 环境变量提供禅道密码")
        sys.exit(1)

    # 解析output.xml
    print(f"[信息] 解析: {args.xml}")
    test_results = parse_robot_output(args.xml)
    overall = "pass" if all(r["status"] == "PASS" for r in test_results) else "fail"
    steps_info = build_steps_info(test_results)
    print(f"[信息] 测试结果: {overall}, 共 {len(test_results)} 个用例")
    print(steps_info)
    print()

    # 构建步骤结果
    step_results = build_step_results(test_results)

    # 同步禅道
    case_ids = [cid.strip() for cid in args.case_id.split(",")]
    sync = ZentaoSync(args.url, args.user, args.pwd)
    sync.login()

    for case_id in case_ids:
        # 提取失败消息
        fail_msg = ""
        for r in test_results:
            if r["status"] == "FAIL" and r["message"]:
                fail_msg = r["message"][:300]
                break
        success = sync.update_test_result(case_id, overall, step_results, fail_msg)
        if not success:
            print(f"[警告] 用例 {case_id} 同步失败，请手动更新")


if __name__ == "__main__":
    main()
