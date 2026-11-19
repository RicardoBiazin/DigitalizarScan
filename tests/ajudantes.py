"""Ajudantes das suites: sem pytest, de proposito (cada suite e' um processo)."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Toda suite isola as preferencias: nunca toca no %APPDATA% de verdade.
os.environ["DIGITALIZARSCAN_CONFIG"] = os.path.join(tempfile.mkdtemp(prefix="dscan-cfg-"), "c.json")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_falhas: list[str] = []
_total = 0


def verificar(condicao, mensagem: str) -> None:
    global _total
    _total += 1
    if not condicao:
        _falhas.append(mensagem)
        print(f"  FALHA: {mensagem}")


def igual(obtido, esperado, mensagem: str) -> None:
    verificar(obtido == esperado, f"{mensagem}: obtido {obtido!r}, esperado {esperado!r}")


def levanta(excecao, funcao, mensagem: str) -> None:
    global _total
    _total += 1
    try:
        funcao()
    except excecao:
        return
    except Exception as exc:                        # noqa: BLE001
        _falhas.append(f"{mensagem}: levantou {type(exc).__name__}, esperado {excecao.__name__}")
        print(f"  FALHA: {_falhas[-1]}")
        return
    _falhas.append(f"{mensagem}: nao levantou {excecao.__name__}")
    print(f"  FALHA: {_falhas[-1]}")


def pasta_nova() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix="dscan-t-"))


def encerrar() -> None:
    print(f"{_total - len(_falhas)}/{_total} verificacoes ok")
    sys.exit(1 if _falhas else 0)


def abrir(caminho):
    """Abre, carrega e solta o arquivo (o Windows nao deixa apagar arquivo aberto)."""
    from PIL import Image
    imagem = Image.open(caminho)
    imagem.load()
    imagem.fp and imagem.fp.close() if getattr(imagem, "fp", None) else None
    return imagem
