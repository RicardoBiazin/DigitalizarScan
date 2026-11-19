"""Idiomas da interface: pt (referencia), en, es e zh (chines simplificado).

Sem gettext: cada idioma e' um dicionario Python em `digitalizarscan/idiomas/`. `t("chave")`
devolve o texto no idioma atual; chave ausente cai no portugues e, no pior caso, na propria
chave (nunca explode na tela do usuario). Marcadores `{n}` sao preenchidos por `t(chave, n=3)`.
"""

from __future__ import annotations

import locale
import os
import sys

from digitalizarscan.idiomas import en, es, pt, zh

IDIOMAS = ("pt", "en", "es", "zh")
#: Nomes proprios, no proprio idioma: o menu de idioma nunca depende do idioma atual.
NOMES = {"pt": "Português", "en": "English", "es": "Español", "zh": "中文"}
#: Idioma de partida e de reserva. Os testes rodam em pt sem configurar nada.
PADRAO = "pt"

#: Codigo de idioma primario do Windows (LANGID & 0x3FF) -> nosso codigo.
_LANG_WINDOWS = {0x16: "pt", 0x09: "en", 0x0A: "es", 0x04: "zh"}
_PREFIXO_LOCALE = ("pt", "en", "es", "zh")

_atual = PADRAO
_catalogos: dict[str, dict[str, str]] = {
    "pt": pt.CATALOGO, "en": en.CATALOGO, "es": es.CATALOGO, "zh": zh.CATALOGO}


def catalogo(codigo: str) -> dict[str, str]:
    if codigo not in _catalogos:
        raise ValueError(f"idioma desconhecido: {codigo!r}")
    return _catalogos[codigo]


def detectar(langid: int | None = None, nome_locale: str | None = None) -> str:
    """Idioma do sistema entre os suportados; qualquer outro vira ingles.

    `langid` e `nome_locale` existem para os testes (None = perguntar ao Windows/ambiente).
    """
    if langid is None and nome_locale is None:
        if sys.platform == "win32":
            try:
                import ctypes
                langid = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
            except Exception:           # noqa: BLE001 - sem ctypes/Windows: cai no locale
                langid = None
        if langid is None:
            nome_locale = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
            if not nome_locale:
                try:
                    nome_locale = locale.getlocale()[0] or ""
                except (ValueError, TypeError):
                    nome_locale = ""
    if langid is not None:
        return _LANG_WINDOWS.get(langid & 0x3FF, "en")
    prefixo = (nome_locale or "").lower().replace("-", "_").split("_")[0]
    return prefixo if prefixo in _PREFIXO_LOCALE else "en"


def definir_idioma(codigo: str) -> str:
    """Escolhe o idioma (`auto` = o do sistema). Devolve o codigo realmente aplicado."""
    global _atual
    if codigo == "auto":
        codigo = detectar()
    if codigo not in IDIOMAS:
        codigo = PADRAO
    _atual = codigo
    return codigo


def idioma_atual() -> str:
    return _atual


def t(chave: str, **valores) -> str:
    texto = catalogo(_atual).get(chave)
    if texto is None:
        texto = catalogo(PADRAO).get(chave, chave)
    if not valores:
        return texto
    try:
        return texto.format(**valores)
    except (KeyError, IndexError, ValueError):
        return texto
