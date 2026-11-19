"""Junta o eSCL (rede) e o WIA (USB e drivers do Windows) numa lista so'.

O eSCL vem primeiro: quando a mesma multifuncional aparece pelos dois caminhos, o da rede e' o
que entrega todas as folhas do alimentador. O WIA continua para scanner USB e para quem nao
fala eSCL. O nome do dispositivo WSD no WIA (ex.: "SCANNER01 (HP OfficeJet...)") vira dica de
nome de rede para o eSCL procurar (SCANNER01.local).
"""

from __future__ import annotations

import re
from typing import Callable, Iterator

from PIL import Image

from digitalizarscan import log_interno
from digitalizarscan.i18n import t
from digitalizarscan.scanner.base import Capacidades, Dispositivo, ErroScanner, EstadoScanner, Opcoes
from digitalizarscan.scanner.escl import PREFIXO, ScannerEscl

log = log_interno.obter(__name__)

_DICA = re.compile(r"^([A-Za-z0-9][A-Za-z0-9-]{2,})\s*\(")


def dicas_de_nome(dispositivos: list[Dispositivo]) -> list[str]:
    dicas = []
    for d in dispositivos:
        m = _DICA.match(d.nome)
        if m and m.group(1) not in dicas:
            dicas.append(m.group(1))
    return dicas


class ScannerComposto:
    def __init__(self, wia, escl: ScannerEscl):
        self._wia = wia
        self._escl = escl

    def _de(self, dispositivo_id: str):
        return self._escl if dispositivo_id.startswith(PREFIXO) else self._wia

    def preparar_thread(self) -> None:
        self._wia.preparar_thread()

    def encerrar_thread(self) -> None:
        self._wia.encerrar_thread()

    def listar(self) -> list[Dispositivo]:
        try:
            pelo_wia = self._wia.listar()
            erro_wia = None
        except ErroScanner as exc:
            pelo_wia, erro_wia = [], exc
        self._escl.dicas = dicas_de_nome(pelo_wia)
        pela_rede = self._escl.listar()
        if not pela_rede and not pelo_wia and erro_wia is not None:
            raise erro_wia
        wia = [Dispositivo(d.id, t("wia.nome", nome=d.nome)) for d in pelo_wia]
        return pela_rede + wia

    def capacidades(self, dispositivo_id: str) -> Capacidades:
        return self._de(dispositivo_id).capacidades(dispositivo_id)

    def digitalizar(self, dispositivo_id: str, opcoes: Opcoes,
                    cancelado: Callable[[], bool]) -> Iterator[Image.Image]:
        return self._de(dispositivo_id).digitalizar(dispositivo_id, opcoes, cancelado)

    def diagnostico(self, dispositivo_id: str) -> str:
        return self._de(dispositivo_id).diagnostico(dispositivo_id)

    def estado(self, dispositivo_id: str) -> EstadoScanner:
        """So' o eSCL informa o papel; o WIA do WSD nao e' confiavel para isso."""
        if dispositivo_id.startswith(PREFIXO):
            return self._escl.estado(dispositivo_id)
        return EstadoScanner(papel=None)

    def previa(self, dispositivo_id: str):
        alvo = self._de(dispositivo_id)
        if not hasattr(alvo, "previa"):
            raise ErroScanner(t("erro.previa_nao_suportada"))
        return alvo.previa(dispositivo_id)
