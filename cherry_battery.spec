# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['cherry_battery.py'],
    pathex=[],
    binaries=[('E:/hidap/x64/hidapi.dll', '.')],
    datas=[
        ('icon_0.png', '.'),
        ('icon_1.png', '.'),
        ('icon_2.png', '.'),
        ('icon_3.png', '.'),
        ('icon_4.png', '.'),
        ('icon_5.png', '.'),
        ('icon_6.png', '.'),
    ],
    hiddenimports=['pystray._win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cherry_battery',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)