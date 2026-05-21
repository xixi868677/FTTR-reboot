"""继电器控制库 - 通过USB转串口控制继电器的开关"""

import serial
import time


class RelayController:
    """Robot Framework库：控制USB转串口继电器"""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._serial = None

    def connect_relay(self, port="COM3", baudrate=9600):
        """连接继电器串口"""
        self._serial = serial.Serial(port, baudrate, timeout=5)
        time.sleep(1)

    def disconnect_relay(self):
        """断开继电器串口连接"""
        if self._serial and self._serial.is_open:
            self._serial.close()

    def send_relay_on(self):
        """发送继电器打开指令（上电）：A0 02 01 A3"""
        self._send_hex("A00201A3")

    def send_relay_off(self):
        """发送继电器关闭指令（断电）：A0 02 00 A2"""
        self._send_hex("A00200A2")

    def _send_hex(self, hex_str):
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("继电器串口未连接，请先调用 Connect Relay")
        data = bytes.fromhex(hex_str)
        self._serial.write(data)
        self._serial.flush()
        time.sleep(0.5)
