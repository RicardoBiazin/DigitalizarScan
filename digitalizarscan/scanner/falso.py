"""Scanner de mentira: gera paginas sinteticas. Usado na suite e em --demo."""

from __future__ import annotations

from typing import Callable, Iterator

from PIL import Image, ImageDraw, ImageFont

from digitalizarscan.i18n import t
from digitalizarscan.scanner.base import (PAPEIS_MM, Capacidades, Dispositivo,
                                          ErroScanner, EstadoScanner, Opcoes)

#: Texto que o OCR deve achar nas paginas geradas.
PALAVRAS = ("RELATORIO", "FATURA", "CONTRATO", "PROTOCOLO", "RECIBO", "LAUDO")
#: Tamanho do vidro do scanner de teste (A4 largo), em mm.
VIDRO_MM = (216.0, 297.0)


class ScannerFalso:
    def __init__(self, folhas_no_alimentador: int = 3, erro: str | None = None,
                 dispositivos: int = 1):
        self.folhas = folhas_no_alimentador
        self.erro = erro
        self._dispositivos = dispositivos
        self.chamadas: list[Opcoes] = []
        self.papel_no_alimentador: bool | None = None

    def preparar_thread(self) -> None:
        pass

    def encerrar_thread(self) -> None:
        pass

    def listar(self) -> list[Dispositivo]:
        return [Dispositivo(f"falso-{i}", t("demo.nome", n=i + 1))
                for i in range(self._dispositivos)]

    def capacidades(self, dispositivo_id: str) -> Capacidades:
        return Capacidades(origens=("vidro", "alimentador", "duplex"), vidro_mm=VIDRO_MM)

    def estado(self, dispositivo_id: str) -> EstadoScanner:
        return EstadoScanner(papel=self.papel_no_alimentador)

    def previa(self, dispositivo_id: str) -> Image.Image:
        """O vidro inteiro a 75 dpi, com a pagina de teste desenhada na area A4."""
        largura, altura = (round(v / 25.4 * 75) for v in VIDRO_MM)
        vidro = Image.new("RGB", (largura, altura), (235, 235, 235))
        vidro.paste(self._pagina(1, Opcoes(dpi=75, cor="cor")), (0, 0))
        return vidro

    def diagnostico(self, dispositivo_id: str) -> str:
        return f"diagnostico do scanner de demonstracao: {dispositivo_id}\n"

    def _pagina(self, numero: int, opcoes: Opcoes) -> Image.Image:
        medida = PAPEIS_MM.get(opcoes.papel) or PAPEIS_MM["A4"]
        if opcoes.regiao_mm and opcoes.origem == "vidro":
            medida = opcoes.regiao_mm[2:]
        largura = round(medida[0] / 25.4 * opcoes.dpi)
        altura = round(medida[1] / 25.4 * opcoes.dpi)
        imagem = Image.new("RGB", (largura, altura), "white")
        pincel = ImageDraw.Draw(imagem)
        tamanho = max(24, opcoes.dpi // 3)
        fonte = ImageFont.load_default(size=tamanho)
        palavra = PALAVRAS[(numero - 1) % len(PALAVRAS)]
        pincel.text((largura // 10, altura // 10), f"{palavra} {numero}",
                    fill=(20, 20, 20), font=fonte)
        pincel.rectangle((largura // 10, altura // 3, largura * 9 // 10, altura // 3 + tamanho),
                         fill=(60, 140, 200))
        if opcoes.cor == "cinza":
            return imagem.convert("L")
        if opcoes.cor == "pb":
            return imagem.convert("L").point(lambda v: 255 if v > 128 else 0).convert("1")
        return imagem

    def digitalizar(self, dispositivo_id: str, opcoes: Opcoes,
                    cancelado: Callable[[], bool]) -> Iterator[Image.Image]:
        self.chamadas.append(opcoes)
        if self.erro:
            raise ErroScanner(self.erro)
        if opcoes.origem == "vidro":
            total = 1
        elif opcoes.origem == "duplex":
            total = self.folhas * 2
        else:
            total = self.folhas
        for numero in range(1, total + 1):
            if cancelado():
                return
            yield self._pagina(numero, opcoes)
