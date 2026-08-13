# Cherry 键盘电量托盘工具

Windows 系统托盘工具，实时显示 Cherry 无线键盘电量。**无需安装 Cherry 官方软件**，直接读取 USB 接收器（dongle）的 HID 数据。

[English Documentation](README.md)

## 特性

- 常驻系统托盘，实时显示电量图标
- 通过 HID 协议直接读取 dongle 数据，不依赖 Cherry Utility
- 自动检测设备名称（如 CHERRY MX 2.0S Dongle）
- 6 档电池图标可视化电量
- 低电量自动提醒（≤20%）
- 休眠检测（键盘闲置时图标变暗）
- 轮询间隔可调（5 / 10 / 20 / 30 / 60 秒，默认 30 秒）
- 配置持久化，重启后自动恢复
- 设备未连接时显示红叉提示

## 支持设备

已在以下设备测试通过：

- Cherry MX 2.0S（VID=0x046A, PID=0x01AC）

理论上支持所有使用 Cherry dongle 的键盘，只要 HID 枚举能找到 `usage_page=0xFF1C` 的 vendor-specific 接口即可。

## 下载使用

### 方式一：直接下载 exe（推荐）

从 [Releases](../../releases) 页面下载 `cherry_battery.exe`，双击运行即可，无需安装 Python 环境。

首次运行会在 exe 同目录生成 `config.json` 保存配置。

### 方式二：从源码运行

```bash
# 依赖
pip install hid pillow pystray

# 还需要 hidapi.dll，放到脚本目录或通过系统 PATH 加载
# 下载地址: https://github.com/libusb/hidapi/releases

# 运行
python cherry_battery.py
```

> 脚本默认从 `E:\hidap\x64` 加载 hidapi.dll，如你的路径不同，请修改 cherry_battery.py 顶部的 `os.add_dll_directory()` 调用。

## 右键菜单

| 菜单项 | 功能 |
|--------|------|
| 刷新 | 手动查询当前电量 |
| 轮询间隔 | 切换自动查询频率（5/10/20/30/60 秒） |
| 退出 | 关闭程序 |

## 工作原理

1. 通过 `hid.enumerate()` 查找 Cherry dongle 的 vendor-specific 接口（Col04, usage_page=0xFF1C）
2. 发送电量查询命令 `04 20 00 1A 06`（64 字节 Output Report）
3. 读取 dongle 返回的状态消息，`byte[8]` 即电量百分比
4. 后台线程按设定间隔轮询，更新托盘图标和 tooltip

命令序列通过 Frida 逆向分析 Cherry 官方软件的 HID 通信得出，详见[开发笔记](#开发笔记)。

## 会对键盘造成干扰吗

不会。工具只操作 Col04 管理接口，不触碰键盘输入所在的 Col01 接口；每次查询只发 1 条 64 字节命令、收 1 条回复，耗时 <1ms，30 秒才查一次，对续航和输入的影响可忽略。

## 从源码打包 exe

```bash
pip install pyinstaller
python -m PyInstaller cherry_battery.spec --noconfirm
```

打包产物在 `dist/cherry_battery.exe`，包含 hidapi.dll 和 7 个电池图标 PNG。exe 图标使用 `logo.ico`。

## 项目结构

```
cherry-battery/
├── cherry_battery.py        # 主程序
├── cherry_battery.spec      # PyInstaller 打包配置
├── logo.png / logo.ico      # 应用 logo（exe 图标）
├── icon_0.png ~ icon_6.png  # 电池图标（0=空, 3=充电, 6=满）
└── README.md                # 英文文档（主）
└── README.zh-CN.md          # 中文文档
```

## 开发笔记

### 如何逆向 Cherry 官方软件

Cherry Utility 通过 HID 与 dongle 通信，但官方软件不开放协议文档。为了不依赖官方软件，使用 [Frida](https://frida.re/) 动态插桩抓取通信内容：

1. 用 Frida spawn 模式启动 Cherry Utility
2. Hook `WriteFile` 和 `ReadFile` API，记录所有 HID 读写
3. 分析抓到的数据包，定位电量查询命令

关键发现：Cherry 软件用 **Output Report**（而非 Feature Report）发送命令，所以单纯监听 Input Report 只能看到回显，会漏掉发送的命令。电量查询命令只有一条：`04 20 00 1A 06`。

### 为什么默认 30 秒轮询

Cherry 官方软件是每 5 秒查一次电量 + 每 3 秒发一次心跳，频率是本工具的 10 倍。30 秒间隔下键盘的无线功耗主要由按键传输决定，电量查询的额外开销测量不出来。如需更省电可在右键菜单调到 60 秒。

## 许可证

MIT License

## 构建工具

本项目完全使用 [Trae](https://www.trae.ai/) 配合 **GLM-5.2** 模型完成 —— 从逆向分析 Cherry 官方软件的 HID 协议，到实现托盘应用、打包 exe，全程无人工编写代码。

## 致谢

- [hidapi](https://github.com/libusb/hidapi) - 跨平台 HID 通信库
- [pystray](https://github.com/moses-palmer/pystray) - Python 系统托盘库
- [Pillow](https://python-pillow.org/) - 图像处理库