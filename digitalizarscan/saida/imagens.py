"""JPG ou PNG, um arquivo por pagina."""

from __future__ import annotations

import pathlib
from typing import Sequence

from PIL import Image

from digitalizarscan.saida.atomico import gravar_atomico

FORMATOS = {"jpg": ("JPEG", ".jpg"), "png": ("PNG", ".png")}


def nomes_de_saida(destino: pathlib.Path, total: int, formato: str) -> list[pathlib.Path]:
    """Um nome so' para 1 pagina; `base_001`, `base_002`... para varias."""
    extensao = FORMATOS[formato][1]
    base = destino.with_suffix("")
    if total == 1:
        return [base.with_suffix(extensao)]
    largura = max(3, len(str(total)))
    return [base.parent / f"{base.name}_{i:0{largura}d}{extensao}" for i in range(1, total + 1)]


def gravar_imagens(paginas: Sequence[pathlib.Path], destino: pathlib.Path, formato: str,
                   dpi: int) -> list[pathlib.Path]:
    if formato not in FORMATOS:
        raise ValueError(f"formato desconhecido: {formato}")
    if not paginas:
        raise ValueError("nenhuma pagina para gravar")
    nome_pillow = FORMATOS[formato][0]
    alvos = nomes_de_saida(pathlib.Path(destino), len(paginas), formato)
    for origem, alvo in zip(paginas, alvos):
        with Image.open(origem) as imagem:
            imagem.load()
            if nome_pillow == "JPEG" and imagem.mode == "1":
                imagem = imagem.convert("L")
            with gravar_atomico(alvo) as temporario:
                imagem.save(temporario, nome_pillow, dpi=(dpi, dpi),
                            **({"quality": 90} if nome_pillow == "JPEG" else {}))
    return alvos
