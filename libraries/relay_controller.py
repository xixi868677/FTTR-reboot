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
        self._close_port()
        time.sleep(0.5)

        for attempt in range(5):
            try:
                self._serial = serial.Serial()
                self._serial.port = port
                self._serial.baudrate = int(baudrate)
                self._serial.timeout = 5
                self._serial.dtr = False
                self._serial.rts = False
                self._serial.open()
                time.sleep(0.5)
                if self._serial.is_open:
                    return
            except serial.SerialException as e:
                self._close_port()
                if attempt < 4:
                    time.sleep(2)
                    continue
                raise RuntimeError(
                    f"Cannot open relay port {port} after 5 attempts: {e}"
                )

    def disconnect_relay(self):
        """断开继电器串口连接"""
        self._close_port()

    def send_relay_on(self):
        """发送继电器打开指令（上电）：A0 02 01 A3"""
        self._send_hex("A00201A3")

    def send_relay_off(self):
        """发送继电器关闭指令（断电）：A0 02 00 A2"""
        self._send_hex("A00200A2")

    def _close_port(self):
        if self._serial:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _send_hex(self, hex_str):
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Relay port not connected, call Connect Relay first")
        data = bytes.fromhex(hex_str)
        self._serial.write(data)
        self._serial.flush()
        time.sleep(0.3)
