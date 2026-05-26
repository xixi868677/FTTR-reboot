"""快速检查设备上dump.txt是否存在"""

import telnetlib
import time
import sys


def check_dump_exists(host="192.168.1.1", user="admin", password="admin@123",
                      root_password="aDm8H%MdA", dump_file="/tmp/dump.txt"):
    try:
        tn = telnetlib.Telnet(host, timeout=10)
        tn.read_until(b"ogin:", timeout=5)
        tn.write(user.encode() + b"\n")
        tn.read_until(b"assword:", timeout=5)
        tn.write(password.encode() + b"\n")
        tn.read_until(b"$", timeout=5)
        tn.write(b"su root\n")
        tn.read_until(b"assword:", timeout=5)
        tn.write(root_password.encode() + b"\n")
        time.sleep(1)
        tn.read_until(b"$", timeout=5)
        tn.write(f"ls -la {dump_file} 2>&1\n".encode())
        time.sleep(2)
        output = tn.read_until(b"$", timeout=10).decode("utf-8", errors="ignore")
        tn.write(b"exit\n")
        tn.write(b"exit\n")
        tn.close()

        if "No such file" in output:
            print(f"[FAIL] {dump_file} NOT FOUND")
        else:
            print(f"[OK] {dump_file} EXISTS")
        print(output.strip())
        return "No such file" not in output
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.1"
    check_dump_exists(host)
