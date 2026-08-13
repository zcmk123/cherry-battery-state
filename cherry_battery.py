#!/usr/bin/env python
"""
Cherry MX 2.0S 键盘电量托盘工具
常驻系统托盘，实时显示键盘电量。无需 Cherry 官方软件。
用法: python cherry_battery.py
"""
import os
import sys
import json
import time
import threading

# 加载 hidapi DLL（支持脚本运行和 PyInstaller exe 两种模式）
if getattr(sys, 'frozen', False):
    os.add_dll_directory(sys._MEIPASS)
    _APP_DIR = os.path.dirname(sys.executable)
else:
    os.add_dll_directory(r"E:\hidap\x64")
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

import hid

import pystray
from PIL import Image, ImageDraw, ImageOps

CHERRY_VID = 0x046A
CHERRY_PID = 0x01AC
DEFAULT_POLL_INTERVAL = 30  # 默认轮询间隔（秒）
POLL_INTERVAL_CHOICES = [5, 10, 20, 30, 60]
LOW_BATTERY_THRESHOLD = 20
CONFIG_FILE = os.path.join(_APP_DIR, "config.json")

# 电量查询命令：发送到 Col04，dongle 回复 0x20 消息，byte[8]=电量百分比
# 通过 Frida 抓包 Cherry 软件获得，无需 Cherry 软件运行
BATTERY_QUERY = bytes([0x04, 0x20, 0x00, 0x1A, 0x06] + [0] * 59)


# ============================================================
#  配置读写
# ============================================================

def load_config():
    """读取配置文件，失败返回默认值"""
    defaults = {"poll_interval": DEFAULT_POLL_INTERVAL}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg.get("poll_interval"), int) and cfg["poll_interval"] in POLL_INTERVAL_CHOICES:
            defaults["poll_interval"] = cfg["poll_interval"]
    except Exception:
        pass
    return defaults


def save_config(cfg):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============================================================
#  HID 通信层
# ============================================================

def find_col04():
    """找到 Col04 vendor-specific 接口"""
    ff1c_devs = [d for d in hid.enumerate(CHERRY_VID, CHERRY_PID)
                 if d["usage_page"] == 0xFF1C]
    if not ff1c_devs:
        return None
    for d in ff1c_devs:
        path = d["path"]
        ps = path.decode("utf-8", errors="ignore") if isinstance(path, bytes) else str(path)
        if "Col04" in ps:
            return d
    return ff1c_devs[0]


def get_device_name():
    """从 HID 设备信息读取真实设备名，失败返回默认名"""
    try:
        dev_info = find_col04()
        if dev_info:
            product = dev_info.get("product_string", "").strip()
            manufacturer = dev_info.get("manufacturer_string", "").strip()
            if product:
                return f"{manufacturer} {product}".strip()
    except Exception:
        pass
    return "Cherry Keyboard"


def read_battery_once(timeout=3.0):
    """
    发送电量查询命令并读取回复。
    打开 Col04 -> 发送 0x20 查询 -> 读取 0x20 回复 -> 返回电量。
    返回: (battery:int, keyboard_active:bool)
      battery=None, active=None  -> 设备不可用
      battery=None, active=False -> 收到数据但无电量回复
      battery=int,   active=True -> 成功读取电量
    """
    dev_info = find_col04()
    if not dev_info:
        return None, None

    try:
        dev = hid.Device(path=dev_info["path"])
        dev.nonblocking = True
    except Exception:
        return None, None

    try:
        # 排空缓冲区
        for _ in range(5):
            dev.read(256, timeout=20)

        # 发送电量查询命令
        try:
            dev.write(BATTERY_QUERY)
        except Exception:
            pass

        start = time.time()
        battery = None
        got_any_data = False
        while time.time() - start < timeout:
            try:
                data = dev.read(256, timeout=300)
                if not data or len(data) < 9:
                    continue
                if not any(b != 0 for b in data):
                    continue

                got_any_data = True
                msg_type = data[1]
                if msg_type == 0x20 and data[8] > 0:
                    return data[8], True
            except Exception:
                continue

        if got_any_data:
            return None, False
        return None, None
    finally:
        dev.close()


# ============================================================
#  图标加载
# ============================================================

def _get_icon_dir():
    """获取图标资源目录（打包时从 _MEIPASS 加载）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return _APP_DIR

# 预加载 7 个电池图标（icon_0=空 ~ icon_6=满，icon_3=充电中）
_BATTERY_ICONS = []
for _i in range(7):
    _p = os.path.join(_get_icon_dir(), f"icon_{_i}.png")
    try:
        _BATTERY_ICONS.append(Image.open(_p).convert("RGBA"))
    except Exception:
        _BATTERY_ICONS.append(None)

# 电量映射使用的图标索引（排除 icon_3 充电图标）
_BATTERY_LEVEL_ICONS = [0, 1, 2, 4, 5, 6]


def create_icon_image(battery, sleeping=False):
    """根据电量返回对应的电池图标 PNG"""
    if battery is None:
        # 未连接：空电池图标 + 红叉
        img = (_BATTERY_ICONS[0].copy() if _BATTERY_ICONS[0]
               else Image.new('RGBA', (64, 64), (0, 0, 0, 0)))
        draw = ImageDraw.Draw(img)
        cx, cy, r = 32, 32, 10
        draw.line([cx - r, cy - r, cx + r, cy + r], fill=(220, 60, 50), width=3)
        draw.line([cx - r, cy + r, cx + r, cy - r], fill=(220, 60, 50), width=3)
        return img

    # 6 档电量映射到图标
    level = min(5, battery * 6 // 100)
    idx = _BATTERY_LEVEL_ICONS[level]
    icon = _BATTERY_ICONS[idx]
    if icon is None:
        return Image.new('RGBA', (64, 64), (0, 0, 0, 0))

    if sleeping:
        # 休眠时转灰度
        gray = ImageOps.grayscale(icon).convert("RGBA")
        return Image.blend(icon, gray, 0.6)

    return icon.copy()


# ============================================================
#  托盘应用
# ============================================================

class TrayApp:
    def __init__(self):
        self.battery = None
        self.connected = False
        self.sleeping = True
        self.icon = None
        self._lock = threading.Lock()
        self._notified_low = False
        # 设备名称（从 HID 读取，如 "CHERRY MX 2.0S Dongle"）
        self.device_name = get_device_name()
        # 轮询间隔配置（可运行时修改）
        self.poll_interval = load_config()["poll_interval"]
        self._wait = threading.Event()  # 用于切换间隔时立即唤醒轮询

    def get_tooltip(self):
        if not self.connected:
            return f"{self.device_name}: 未连接"
        if self.battery is None:
            return f"{self.device_name}: 等待数据..."
        if self.sleeping:
            return f"{self.device_name}: {self.battery}% (休眠)"
        return f"{self.device_name}: {self.battery}%"

    def update_state(self, battery=None, connected=None, sleeping=None):
        """更新状态并刷新图标"""
        with self._lock:
            if connected is not None:
                self.connected = connected
            if battery is not None:
                self.battery = battery
            if sleeping is not None:
                self.sleeping = sleeping

        if self.icon:
            self.icon.icon = create_icon_image(self.battery, self.sleeping)
            self.icon.title = self.get_tooltip()

        if battery is not None and battery <= LOW_BATTERY_THRESHOLD:
            if not self._notified_low:
                self._notified_low = True
                if self.icon:
                    self.icon.notify(f"键盘电量低: {battery}%，请及时充电", self.device_name)
        elif battery is not None and battery > LOW_BATTERY_THRESHOLD:
            self._notified_low = False

    def poll_loop(self):
        """后台轮询线程，间隔可运行时修改"""
        while True:
            dev_info = find_col04()
            if not dev_info:
                self.update_state(connected=False, sleeping=True)
                # 未连接时固定 5 秒重试
                if self._wait.wait(timeout=5):
                    self._wait.clear()
                continue

            self.update_state(connected=True)

            battery, active = read_battery_once(timeout=3.0)

            if battery is not None:
                self.update_state(battery=battery, sleeping=False)
            elif active is False:
                self.update_state(sleeping=True)
            else:
                pass

            # 按配置间隔等待；切换间隔时 set() 可立即唤醒
            if self._wait.wait(timeout=self.poll_interval):
                self._wait.clear()

    def on_refresh(self, icon, item):
        """手动刷新"""
        def do_refresh():
            battery, active = read_battery_once(timeout=4.0)
            if battery is not None:
                self.update_state(battery=battery, sleeping=False)
                icon.notify(f"当前电量: {battery}%", self.device_name)
            elif not self.connected:
                icon.notify("未检测到 USB 接收器", self.device_name)
            elif active is False:
                self.update_state(sleeping=True)
                icon.notify("键盘休眠中，按任意键唤醒后刷新", self.device_name)
            else:
                icon.notify("读取失败，请重试", self.device_name)

        threading.Thread(target=do_refresh, daemon=True).start()

    def on_set_interval(self, icon, item):
        """切换轮询间隔，保存配置并立即生效"""
        seconds = int(item.text.split()[0])
        self.poll_interval = seconds
        save_config({"poll_interval": seconds})
        # 唤醒轮询线程使新间隔立即生效
        self._wait.set()
        icon.notify(f"轮询间隔已设为 {seconds} 秒", self.device_name)

    def on_exit(self, icon, item):
        icon.stop()

    def run(self):
        # 轮询间隔子菜单，当前选中项打勾
        interval_items = [
            pystray.MenuItem(
                f"{s} 秒",
                self.on_set_interval,
                radio=True,
                checked=lambda item, s=s: self.poll_interval == s,
            )
            for s in POLL_INTERVAL_CHOICES
        ]

        menu = pystray.Menu(
            pystray.MenuItem("刷新电量", self.on_refresh, default=True),
            pystray.MenuItem("轮询间隔", pystray.Menu(*interval_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self.on_exit),
        )

        self.icon = pystray.Icon(
            "cherry_battery",
            create_icon_image(None),
            f"{self.device_name}: 启动中...",
            menu,
        )

        threading.Thread(target=self.poll_loop, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    TrayApp().run()
