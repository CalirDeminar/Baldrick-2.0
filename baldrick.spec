# -*- mode: python ; coding: utf-8 -*-
import glob
import os
import sysconfig

from PyInstaller.utils.hooks import collect_all

# libvips ships as loose files in site-packages root via the pyvips_binary
# (delvewheel) wheel: the compiled cffi extension (_libvips*.pyd), the mangled
# libvips DLL and a .load-order file the extension reads on import. PyInstaller
# does not detect these automatically, so collect them explicitly.
_site = sysconfig.get_paths()["purelib"]
_vips_binaries = [
    (p, ".")
    for p in glob.glob(os.path.join(_site, "_libvips*.pyd"))
    + glob.glob(os.path.join(_site, "libvips-*.dll"))
]
_vips_datas = [
    (p, ".") for p in glob.glob(os.path.join(_site, ".load-order-pyvips_binary-*"))
]

# mgrs ships its compiled extension as a loose .pyd in site-packages root
# (same layout as libvips). PyInstaller does not detect it automatically.
_mgrs_binaries = [
    (p, ".") for p in glob.glob(os.path.join(_site, "libmgrs*.pyd"))
]

_pyvips_datas, _pyvips_binaries, _pyvips_hidden = collect_all("pyvips")

a = Analysis(
    ['src\\baldrick.py'],
    pathex=['src'],
    binaries=_vips_binaries + _pyvips_binaries + _mgrs_binaries,
    datas=[('./map_data', 'map_data'), ('./assets', 'assets')] + _vips_datas + _pyvips_datas,
    hiddenimports=['_libvips', 'cffi', 'mgrs', 'mgrs.core'] + _pyvips_hidden,
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
    [],
    exclude_binaries=True,
    name='baldrick',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='baldrick',
)
