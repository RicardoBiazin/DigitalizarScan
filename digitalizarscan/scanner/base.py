"""Contrato dos scanners. O resto do programa so' conhece isto, nunca o COM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Protocol

from PIL import Image

#: Tamanhos de papel em milimetros (largura, altura). None = area total do vidro.
PAPEIS_MM: dict[str, tuple[float, float] | None] = {
    "A4": (210.0, 297.0),
    "Carta": (215.9, 279.4),
    "Ofício": (215.9, 330.2),
    "total": None,
}


class ErroScanner(Exception):
    """Falha de digitalizacao com mensagem pronta para mostrar ao usuario."""


@dataclass(frozen=True)
class Dispositivo:
    id: str
    nome: str


@dataclass(frozen=True)
class Capacidades:
    origens: tuple[str, ...] = ("vidro",)
    dpis: tuple[int, ...] = (150, 200, 300, 600)
    #: Largura x altura do vidro em mm, quando o scanner informa (habilita a previa com recorte).
    vidro_mm: tuple[float, float] | None = None


@dataclass(frozen=True)
class EstadoScanner:
    #: True = ha' papel no alimentador, False = vazio, None = o scanner nao informa.
    papel: bool | None = None


@dataclass(frozen=True)
class Opcoes:
    origem: str = "vidro"      # vidro | alimentador | duplex
    cor: str = "cor"           # cor | cinza | pb
    dpi: int = 300
    papel: str = "A4"          # chave de PAPEIS_MM
    #: Area do vidro a digitalizar (x, y, largura, altura em mm, do canto superior esquerdo).
    #: Quando presente, vale no lugar do tamanho do papel. So' faz sentido com origem "vidro".
    regiao_mm: tuple[float, float, float, float] | None = None


def escolher_preferido(dispositivos: list[Dispositivo], preferido: str) -> Dispositivo:
    """O lembrado, salvo quando ele e' WIA e ha' scanner de rede (eSCL): o de rede entrega todas
    as folhas do alimentador, o WIA de impressora de rede (WSD) so' a primeira."""
    rede = [d for d in dispositivos if d.id.startswith("escl:")]
    lembrado = next((d for d in dispositivos if d.id == preferido), None)
    if lembrado is not None and (lembrado.id.startswith("escl:") or not rede):
        return lembrado
    return rede[0] if rede else dispositivos[0]


class Scanner(Protocol):
    def preparar_thread(self) -> None:
        """Chamado no inicio de cada thread que usa o scanner (COM exige)."""

    def encerrar_thread(self) -> None:
        """Par de `preparar_thread`, chamado no fim."""

    def listar(self) -> list[Dispositivo]: ...

    # Opcionais (a janela usa getattr): `estado(id) -> EstadoScanner` e `previa(id) -> Image`.

    def capacidades(self, dispositivo_id: str) -> Capacidades: ...

    def digitalizar(self, dispositivo_id: str, opcoes: Opcoes,
                    cancelado: Callable[[], bool]) -> Iterator[Image.Image]:
        """Gera uma imagem por pagina, ate' acabar o papel ou `cancelado()`."""
        ...
