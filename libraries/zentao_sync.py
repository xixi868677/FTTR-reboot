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
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("token")
            self.session.headers.update({"Token": self.token})
            print(f"[禅道] 登录成功, token: {self.token[:20]}...")
        else:
            raise RuntimeError(f"禅道登录失败: {resp.status_code} {resp.text}")

    def update_test_result(self, case_id, result, steps_info=""):
        """更新测试用例执行结果

        Args:
            case_id: 禅道用例ID
            result: 'pass' 或 'fail'
            steps_info: 步骤信息字符串
        """
        # 尝试禅道开源版API（v1）
        url = f"{self.base_url}/api.php/v1/cases/{case_id}"

        # 先尝试获取用例信息
        resp = self.session.get(url)
        if resp.status_code != 200:
            print(f"[禅道] 获取用例 {case_id} 失败: {resp.status_code} {resp.text[:200]}")
            # 尝试旧版API
            return self._update_test_result_legacy(case_id, result, steps_info)

        # 提交测试结果
        # 禅道的测试结果提交方式因版本而异
        # 这里尝试通过 bug 或 testTask 方式提交
        payload = {
            "result": result,
            "steps": steps_info,
        }
        resp = self.session.post(f"{url}/results", json=payload)
        if resp.status_code in (200, 201):
            print(f"[禅道] 用例 {case_id} 结果已同步: {result}")
            return True
        else:
            print(f"[禅道] API v1提交失败，尝试legacy方式...")
            return self._update_test_result_legacy(case_id, result, steps_info)

    def _update_test_result_legacy(self, case_id, result, steps_info=""):
        """禅道旧版API方式提交结果

        通过创建测试执行结果来同步
        """
        # 先登录获取session
        login_url = f"{self.base_url}/index.php?m=user&f=login"
        self.session.get(login_url)
        resp = self.session.post(login_url, data={
            "account": self.user,
            "password": self.password,
            "keepLogin": "on",
        })

        # 提交测试结果
        # 禅道旧版通过 testtask -> results 提交
        result_map = {"pass": "pass", "fail": "fail", "blocked": "blocked"}
        zentao_result = result_map.get(result, "fail")

        # 尝试直接通过API提交
        url = f"{self.base_url}/api.php/v1/results"
        payload = {
            "case": case_id,
            "result": zentao_result,
            "steps": steps_info,
        }
        resp = self.session.post(url, json=payload)
        if resp.status_code in (200, 201):
            print(f"[禅道] 用例 {case_id} 结果已同步(legacy): {result}")
            return True
        else:
            print(f"[禅道] legacy提交也失败: {resp.status_code} {resp.text[:300]}")
            print(f"[禅道] 请检查禅道版本和API权限，或手动同步结果")
            return False


def parse_robot_output(xml_path):
    """解析Robot Framework output.xml

    Returns:
        list of dict: [{'name': ..., 'status': 'PASS'|'FAIL', 'message': ..., 'elapsed': ...}]
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    results = []

    # 找到所有test元素
    for test in root.iter("test"):
        name = test.get("name", "unknown")
        status_elem = test.find("status")
        status = status_elem.get("status", "UNKNOWN") if status_elem is not None else "UNKNOWN"
        message = status_elem.text.strip() if status_elem is not None and status_elem.text else ""
        elapsed = status_elem.get("elapsed", "0") if status_elem is not None else "0"

        results.append({
            "name": name,
            "status": status,
            "message": message,
            "elapsed": elapsed,
        })

    if not results:
        print(f"[警告] output.xml中未找到测试用例: {xml_path}")

    return results


def build_steps_info(test_results):
    """将测试结果格式化为步骤信息字符串"""
    lines = []
    for i, r in enumerate(test_results, 1):
        lines.append(f"测试{i}: {r['name']} - {r['status']}")
        if r["message"]:
            lines.append(f"  信息: {r['message']}")
        lines.append(f"  耗时: {r.get('elapsed', 'N/A')}秒")
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

    # 同步禅道
    case_ids = [cid.strip() for cid in args.case_id.split(",")]
    sync = ZentaoSync(args.url, args.user, args.pwd)
    sync.login()

    for case_id in case_ids:
        success = sync.update_test_result(case_id, overall, steps_info)
        if not success:
            print(f"[警告] 用例 {case_id} 同步失败，请手动更新")


if __name__ == "__main__":
    main()
