"""Tema de cor: seguir o sistema, claro ou escuro.

O Qt 6.8+ troca as cores de toda a aplicacao por `QStyleHints.setColorScheme`. No Windows 10 o
estilo padrao ("windowsvista") nao acompanha o esquema: nesse caso muda para o Fusion, que
acompanha. `Unknown` devolve a escolha ao sistema.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

MODOS = ("sistema", "claro", "escuro")


def esquema_de(modo: str) -> Qt.ColorScheme:
    return {"claro": Qt.ColorScheme.Light, "escuro": Qt.ColorScheme.Dark}.get(modo, Qt.ColorScheme.Unknown)


def aplicar(aplicacao, modo: str) -> str:
    """Aplica o tema e devolve o modo efetivamente usado."""
    if modo not in MODOS:
        modo = "sistema"
    if aplicacao.style().name().lower() == "windowsvista":
        aplicacao.setStyle("Fusion")
    aplicacao.styleHints().setColorScheme(esquema_de(modo))
    return modo
