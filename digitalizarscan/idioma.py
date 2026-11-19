"""Traducao do proprio Qt (botoes do QMessageBox, QFileDialog, menus de contexto).

Os textos do programa vem do catalogo (`i18n.py`). Os dialogos padrao do Qt tem catalogos `.qm`
que acompanham o PySide6; no executavel o .spec os coloca em `traducoes/`. Falhar em carregar
nao e' erro: so' deixa os botoes desses dialogos em ingles.
"""

from __future__ import annotations

import pathlib
import sys

from digitalizarscan import log_interno

log = log_interno.obter(__name__)

#: Catalogos do Qt por idioma da interface. O ingles e' o do proprio Qt: nada a carregar.
CATALOGOS = {
    "pt": ("qtbase_pt_BR", "qt_pt_BR"),
    "es": ("qtbase_es", "qt_es"),
    "zh": ("qtbase_zh_CN", "qt_zh_CN"),
    "en": (),
}


def pastas_de_traducao() -> list[pathlib.Path]:
    lugares: list[pathlib.Path] = []
    base = getattr(sys, "_MEIPASS", "")
    if base:
        lugares.append(pathlib.Path(base) / "traducoes")
    try:
        import PySide6
        lugares.append(pathlib.Path(PySide6.__file__).parent / "translations")
    except ImportError:
        pass
    return [p for p in lugares if p.is_dir()]


def instalar(aplicacao, codigo: str = "pt") -> list[str]:
    """Troca os catalogos do Qt para `codigo`. Guarda os tradutores no QApplication (senao o
    coletor do Python os destroi e a traducao some). Pode ser chamada de novo ao mudar o idioma."""
    from PySide6.QtCore import QLocale, QTranslator

    locale = {"pt": (QLocale.Language.Portuguese, QLocale.Country.Brazil),
              "en": (QLocale.Language.English, QLocale.Country.UnitedStates),
              "es": (QLocale.Language.Spanish, QLocale.Country.Spain),
              "zh": (QLocale.Language.Chinese, QLocale.Country.China)}.get(
        codigo, (QLocale.Language.English, QLocale.Country.UnitedStates))
    QLocale.setDefault(QLocale(*locale))

    for antigo in getattr(aplicacao, "_tradutores", []):
        aplicacao.removeTranslator(antigo)
    guardados, carregados = [], []
    for pasta in pastas_de_traducao():
        for catalogo in CATALOGOS.get(codigo, ()):
            if catalogo in carregados:
                continue
            tradutor = QTranslator(aplicacao)
            if tradutor.load(catalogo, str(pasta)):
                aplicacao.installTranslator(tradutor)
                guardados.append(tradutor)
                carregados.append(catalogo)
    aplicacao._tradutores = guardados
    if CATALOGOS.get(codigo) and not carregados:
        log.warning("nenhum catalogo de traducao do Qt encontrado para %s", codigo)
    return carregados
