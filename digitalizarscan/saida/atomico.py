"""Gravacao atomica: escreve num temporario ao lado e so' entao troca pelo destino."""

from __future__ import annotations

import os
import pathlib
import tempfile
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def gravar_atomico(destino: pathlib.Path) -> Iterator[pathlib.Path]:
    """Entrega um caminho temporario; ao sair sem erro, ele substitui `destino`.

    Se qualquer coisa falhar no meio, o temporario some e o arquivo que ja' existia
    em `destino` continua intacto.
    """
    destino = pathlib.Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, caminho = tempfile.mkstemp(dir=destino.parent, prefix=".dscan-", suffix=destino.suffix)
    os.close(fd)
    temporario = pathlib.Path(caminho)
    try:
        yield temporario
        os.replace(temporario, destino)
    except BaseException:
        try:
            temporario.unlink()
        except OSError:
            pass
        raise
