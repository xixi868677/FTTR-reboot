"""
企业微信群机器人通知 - 发送测试结果到群聊

用法:
    python wechat_notify.py --xml output.xml
    python wechat_notify.py --xml output.xml --key ae2ab3e2-db1b-4c13-a49d-a3238d016cb9
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET

import requests


WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"


def parse_robot_output(xml_path):
    """解析output.xml，提取测试结果摘要"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    tests = []
    for test in root.iter("test"):
        name = test.get("name", "unknown")
        status_elem = test.find("status")
        status = status_elem.get("status", "UNKNOWN") if status_elem is not None else "UNKNOWN"
        message = status_elem.text.strip() if status_elem is not None and status_elem.text else ""
        elapsed = status_elem.get("elapsed", "0") if status_elem is not None else "0"

        # 收集步骤日志
        step_lines = []
        for msg in root.iter("msg"):
            text = msg.text.strip() if msg.text else ""
            if text and "[步骤" in text and msg.get("level") in ("INFO", "FAIL"):
                step_lines.append(text)

        tests.append({
            "name": name,
            "status": status,
            "message": message,
            "elapsed": float(elapsed),
            "steps": step_lines,
        })

    return tests


def build_markdown_message(tests):
    """构建简短的markdown格式消息"""
    total = len(tests)
    passed = sum(1 for t in tests if t["status"] == "PASS")
    failed = total - passed

    if failed == 0:
        lines = ["#### FTTR断电重启测试 ✅ 通过\n"]
        lines.append(f"> 共{total}个用例全部通过")
    else:
        lines = ["#### FTTR断电重启测试 ❌ 失败\n"]
        for t in tests:
            if t["status"] != "FAIL":
                continue
            lines.append(f"**失败用例**: {t['name']}")
            if t["message"]:
                lines.append(f"> {t['message'][:200]}")
            # 只显示失败的步骤
            for s in t.get("steps", []):
                if "FAIL" in s:
                    lines.append(f"- {s}")
                    break

    return "\n".join(lines)


def send_wechat_message(key, content):
    """发送消息到企业微信群"""
    url = f"{WEBHOOK_URL}?key={key}"
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content,
        }
    }
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("errcode") == 0:
            print("[WeChat] Message sent OK")
            return True
        else:
            print(f"[WeChat] Send failed: {data}")
            return False
    else:
        print(f"[WeChat] HTTP error: {resp.status_code} {resp.text}")
        return False


def main():
    parser = argparse.ArgumentParser(description="发送测试结果到企业微信群")
    parser.add_argument("--xml", required=True, help="Robot Framework output.xml路径")
    parser.add_argument("--key", default=os.getenv("WECHAT_WEBHOOK_KEY",
                        "ae2ab3e2-db1b-4c13-a49d-a3238d016cb9"),
                        help="企业微信群机器人webhook key")
    args = parser.parse_args()

    tests = parse_robot_output(args.xml)
    content = build_markdown_message(tests)
    print(f"[信息] Sending message to WeChat Work group...")
    send_wechat_message(args.key, content)


if __name__ == "__main__":
    main()
