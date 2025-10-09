# -*- mode: python ; coding: utf-8 -*-

import os
block_cipher = None

# Build datas list and include version.txt only when it exists (CI)
datas = [
    ('discontinuations/*.json', 'discontinuations'),
    ('gui_icon.ico', '.'),
    ('helpers/*.py', 'helpers'),
    ('as4_to_as6_analyzer.py', '.'),
    ('checks/*.py', 'checks'),
    ('utils/*.py', 'utils'),
    ('links/*.json', 'links'),
    ('licenses/*.json', 'licenses'),
]
if os.path.isfile('version.txt'):
    datas.append(('version.txt', '.'))

a = Analysis(
    ['gui_launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'CTkMessagebox',
        'tkinter',
        'lxml', 'lxml.etree', 'lxml._elementpath',
        'requests'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='as6-migration-tools',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon='gui_icon.ico',
    bootloader_ignore_signals=False,
)
