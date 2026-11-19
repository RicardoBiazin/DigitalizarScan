"""Conjunto de paginas digitalizadas, sem Qt.

Cada pagina vive num PNG numa pasta temporaria: uma pagina A4 colorida a 300 dpi
tem ~26 MB descompactada, e guardar dezenas na memoria estoura a RAM. Na
memoria fica so' a miniatura.
"""

from __future__ import annotations

import io
import itertools
import os
import pathlib
import shutil
import tempfile
from dataclasses import dataclass

from PIL import Image

LADO_MINIATURA = 240


def pasta_temporaria() -> pathlib.Path:
    """Pasta nova e vazia. Prefere caminho ASCII: o Tesseract no Windows tropeca em acento."""
    candidatas = [None, os.environ.get("PUBLIC")]
    for base in candidatas:
        try:
            if base is not None and not os.path.isdir(base):
                continue
            pasta = pathlib.Path(tempfile.mkdtemp(prefix="dscan-", dir=base))
        except OSError:
            continue
        if str(pasta).isascii():
            return pasta
        shutil.rmtree(pasta, ignore_errors=True)
    return pathlib.Path(tempfile.mkdtemp(prefix="dscan-"))


@dataclass
class Pagina:
    id: int
    caminho: pathlib.Path
    miniatura: bytes          # PNG pequeno
    dpi: int


def _miniatura(imagem: Image.Image) -> bytes:
    copia = imagem.convert("RGB") if imagem.mode not in ("RGB", "L") else imagem.copy()
    copia.thumbnail((LADO_MINIATURA, LADO_MINIATURA))
    saida = io.BytesIO()
    copia.save(saida, "PNG")
    return saida.getvalue()


class Documento:
    def __init__(self, pasta: pathlib.Path | None = None):
        self.pasta = pasta or pasta_temporaria()
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.paginas: list[Pagina] = []
        self._ids = itertools.count(1)

    def __len__(self) -> int:
        return len(self.paginas)

    def adicionar(self, imagem: Image.Image, dpi: int) -> Pagina:
        numero = next(self._ids)
        caminho = self.pasta / f"p{numero:04d}.png"
        # Modos que o PNG grava direto sao mantidos (1, L, RGB); o resto vira RGB.
        if imagem.mode not in ("1", "L", "RGB"):
            imagem = imagem.convert("RGB")
        imagem.save(caminho, "PNG", compress_level=1, dpi=(dpi, dpi))
        pagina = Pagina(numero, caminho, _miniatura(imagem), dpi)
        self.paginas.append(pagina)
        return pagina

    def _indice(self, id_: int) -> int:
        for i, p in enumerate(self.paginas):
            if p.id == id_:
                return i
        raise KeyError(id_)

    def remover(self, id_: int) -> None:
        pagina = self.paginas.pop(self._indice(id_))
        try:
            pagina.caminho.unlink()
        except OSError:
            pass

    def girar(self, id_: int, graus: int) -> None:
        """Gira no sentido horario; `graus` multiplo de 90 (negativo = anti-horario)."""
        pagina = self.paginas[self._indice(id_)]
        with Image.open(pagina.caminho) as original:
            original.load()
            girada = original.rotate(-graus, expand=True)
        girada.save(pagina.caminho, "PNG", compress_level=1, dpi=(pagina.dpi, pagina.dpi))
        pagina.miniatura = _miniatura(girada)

    def reordenar(self, ids: list[int]) -> None:
        """Poe as paginas na ordem de `ids`, que tem de ser exatamente o conjunto atual."""
        por_id = {p.id: p for p in self.paginas}
        if sorted(ids) != sorted(por_id):
            raise ValueError("a nova ordem nao bate com as paginas existentes")
        self.paginas = [por_id[i] for i in ids]

    def limpar(self) -> None:
        for p in self.paginas:
            try:
                p.caminho.unlink()
            except OSError:
                pass
        self.paginas.clear()

    def caminhos(self) -> list[pathlib.Path]:
        return [p.caminho for p in self.paginas]

    def descartar(self) -> None:
        """Apaga a pasta temporaria inteira (ao fechar o programa)."""
        self.paginas.clear()
        shutil.rmtree(self.pasta, ignore_errors=True)
