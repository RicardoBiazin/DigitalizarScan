"""PDF multipagina sem texto reconhecivel (o OCR fica em `ocr.py`)."""

from __future__ import annotations

import pathlib
from typing import Sequence

from PIL import Image

from digitalizarscan.saida.atomico import gravar_atomico


def gravar_pdf(paginas: Sequence[pathlib.Path], destino: pathlib.Path, dpi: int) -> None:
    if not paginas:
        raise ValueError("nenhuma pagina para gravar")
    abertas: list[Image.Image] = []
    try:
        for caminho in paginas:
            imagem = Image.open(caminho)
            imagem.load()
            if imagem.mode not in ("1", "L", "RGB"):
                imagem = imagem.convert("RGB")
            abertas.append(imagem)
        todas_pb = all(i.mode == "1" for i in abertas)
        if not todas_pb:
            # O PDF do Pillow grava "1" em CCITT, que nao aceita `quality` (a mesma chamada vale
            # para todas as paginas): numa mistura, a pagina preto e branco vira cinza.
            abertas = [i.convert("L") if i.mode == "1" else i for i in abertas]
        opcoes = {} if todas_pb else {"quality": 85}
        with gravar_atomico(destino) as temporario:
            abertas[0].save(temporario, "PDF", save_all=True, append_images=abertas[1:],
                            resolution=float(dpi), **opcoes)
    finally:
        for imagem in abertas:
            imagem.close()
