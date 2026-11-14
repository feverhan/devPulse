# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：把后端、依赖与前端静态资源打成单个可执行程序。"""

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

datas = [(os.path.join(ROOT, 'frontend', 'dist'), 'static')]
binaries = []
hiddenimports = []

for pkg in (
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.protocols',
    'pydantic',
    'pydantic_settings',
    'anyio',
    'sqlalchemy',
    'apscheduler',
    'httpx',
    'cryptography',
    'multipart',
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

hiddenimports += [
    'app.main',
    'app.config',
    'app.database',
    'app.models',
    'app.migrations',
    'app.security',
    'app.timeutil',
    'app.routers.auth',
    'app.routers.commits',
    'app.routers.dashboard',
    'app.routers.monitors',
    'app.routers.projects',
    'app.routers.reports',
    'app.routers.repos',
    'app.routers.reviews',
    'app.routers.settings',
    'app.routers.setup',
    'app.routers.works',
    'app.services.config_store',
    'app.services.gitplatform',
    'app.services.llm',
    'app.services.migrate',
    'app.services.monitor',
    'app.services.report',
    'app.services.review',
    'app.services.scheduler',
    'app.services.sync',
    'app.services.task_queue',
]

a = Analysis(
    [os.path.join(ROOT, 'backend', 'standalone.py')],
    pathex=[os.path.join(ROOT, 'backend')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pytest', 'IPython', 'notebook'],
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
    name='devpulse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)