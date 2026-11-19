"""Log em arquivo e captura de excecao nao tratada.

O executavel e' `--windowed`: sem console, um erro some. O log em
%APPDATA%/DigitalizarScan/digitalizarscan.log e' o unico rastro. A fumaca do
build procura a marca "EXCECAO NAO TRATADA" nele.
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys
import traceback

from digitalizarscan import configuracao

_iniciado = False


def pasta_de_dados() -> pathlib.Path:
    return configuracao.pasta_de_dados()


def iniciar() -> None:
    """Liga o log em arquivo e o gancho de excecao. Idempotente."""
    global _iniciado
    if _iniciado:
        return
    _iniciado = True
    raiz = logging.getLogger("digitalizarscan")
    raiz.setLevel(logging.INFO)
    try:
        pasta = pasta_de_dados()
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = logging.FileHandler(pasta / "digitalizarscan.log", encoding="utf-8")
        arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        raiz.addHandler(arquivo)
    except OSError:
        pass  # sem pasta gravavel o programa continua, so' sem log

    anterior = sys.excepthook

    def gancho(tipo, valor, tb):
        raiz.error("EXCECAO NAO TRATADA\n%s", "".join(traceback.format_exception(tipo, valor, tb)))
        if anterior is not None and not getattr(sys, "frozen", False):
            anterior(tipo, valor, tb)

    sys.excepthook = gancho


def obter(nome: str) -> logging.Logger:
    return logging.getLogger(nome if nome.startswith("digitalizarscan") else f"digitalizarscan.{nome}")
