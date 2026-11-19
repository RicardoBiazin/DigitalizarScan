# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller do DigitalizarScan. Quem roda e' o build.bat.

    .venv\\Scripts\\python.exe -m PyInstaller --noconfirm --clean DigitalizarScan.spec

DIGITALIZARSCAN_UM_ARQUIVO=1 gera o executavel unico (build.bat umarquivo); sem a
variavel, gera a pasta one-dir, que e' o que se entrega em ZIP.
"""

import os
import pathlib

import PySide6

RAIZ = pathlib.Path(SPECPATH)
UM_ARQUIVO = os.environ.get("DIGITALIZARSCAN_UM_ARQUIVO") == "1"
TRADUCOES = pathlib.Path(PySide6.__file__).parent / "translations"
ICONE = RAIZ / "digitalizarscan" / "recursos" / "icone.ico"
TESSERACT = RAIZ / "tesseract"

# Modulos que o programa nao usa. Cada um tirado daqui precisa passar na
# autoverificacao do .exe, que o build.bat roda logo depois.
EXCLUDES = [
    "tkinter",
    "matplotlib",
    "numpy",
    "pandas",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.Qt3DCore",
    "pypdf",
]

# DLLs que sobram do PySide6 para uma janela de widgets basicos.
DLLS_DESNECESSARIAS = {
    "opengl32sw.dll",
    "qt6pdf.dll",
    "qt6pdfwidgets.dll",
    "qt6quick.dll",
    "qt6qml.dll",
    "qt6qmlmodels.dll",
    "qt6multimedia.dll",
    "qt6sql.dll",
}

# Catalogos do Qt dos 4 idiomas da interface (o ingles e' o do proprio Qt).
QM = ("qtbase_pt_BR.qm", "qt_pt_BR.qm", "qtbase_es.qm", "qt_es.qm", "qtbase_zh_CN.qm", "qt_zh_CN.qm")
for nome in QM:
    if not (TRADUCOES / nome).is_file():
        raise SystemExit(f"ERRO: {nome} nao esta em {TRADUCOES}")
if not ICONE.is_file():
    raise SystemExit(f"ERRO: {ICONE} nao existe. Rode ferramentas/gerar_icone.py.")

datas = [(str(RAIZ / "digitalizarscan" / "recursos"), "digitalizarscan/recursos")]
datas += [(str(TRADUCOES / nome), "traducoes") for nome in QM]
# O Tesseract vai como DADO (processo separado), nao como biblioteca analisada.
if (TESSERACT / "tesseract.exe").is_file():
    datas.append((str(TESSERACT), "tesseract"))
else:
    print("AVISO: pasta tesseract\\ ausente; o executavel sai SEM OCR embutido. "
          "Rode ferramentas\\baixar_tesseract.ps1.")

a = Analysis(
    [str(RAIZ / "app.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=datas,
    # O COM do WIA e' carregado por nome (Dispatch), entao o analisador nao ve' esses modulos.
    # Os catalogos de idioma sao importados em i18n.py; ficam declarados aqui por garantia.
    hiddenimports=["win32com", "win32com.client", "pythoncom", "pywintypes",
                   "digitalizarscan.idiomas.pt", "digitalizarscan.idiomas.en",
                   "digitalizarscan.idiomas.es", "digitalizarscan.idiomas.zh"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)

_descartar = {nome.lower() for nome in DLLS_DESNECESSARIAS}
a.binaries = [b for b in a.binaries
              if os.path.basename(b[0]).lower() not in _descartar]

pyz = PYZ(a.pure)

if UM_ARQUIVO:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="DigitalizarScan",
        icon=str(ICONE),
        version=str(RAIZ / "versao.txt"),
        manifest=str(RAIZ / "digitalizarscan.manifest"),
        console=False,
        upx=False,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="DigitalizarScan",
        icon=str(ICONE),
        version=str(RAIZ / "versao.txt"),
        manifest=str(RAIZ / "digitalizarscan.manifest"),
        console=False,
        upx=False,
    )
    coleta = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name="DigitalizarScan",
    )
