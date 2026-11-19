"""Preferencias do usuario em JSON.

Arquivo: %APPDATA%/DigitalizarScan/configuracao.json. A variavel
DIGITALIZARSCAN_CONFIG aponta para outro arquivo (e' o que os testes usam: a
suite nunca toca nas preferencias de verdade). Valor ausente, de tipo errado ou
fora da lista volta ao padrao; um JSON quebrado nao derruba o programa.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
from dataclasses import asdict, dataclass, field, fields


def pasta_de_dados() -> pathlib.Path:
    base = os.environ.get("APPDATA") or str(pathlib.Path.home())
    return pathlib.Path(base) / "DigitalizarScan"


def caminho_do_arquivo() -> pathlib.Path:
    forcado = os.environ.get("DIGITALIZARSCAN_CONFIG")
    if forcado:
        return pathlib.Path(forcado)
    return pasta_de_dados() / "configuracao.json"


ORIGENS = ("vidro", "alimentador", "duplex")
CORES = ("cor", "cinza", "pb")
DPIS = (150, 200, 300, 600)
PAPEIS = ("A4", "Carta", "Ofício", "total")
FORMATOS = ("pdf", "jpg", "png")
TEMAS = ("sistema", "claro", "escuro")
IDIOMAS = ("auto", "pt", "en", "es", "zh")


@dataclass
class Configuracao:
    scanner_id: str = ""
    origem: str = "vidro"
    cor: str = "cor"
    dpi: int = 300
    papel: str = "A4"
    formato: str = "pdf"
    ocr: bool = True
    pasta_saida: str = ""
    tema: str = "sistema"
    idioma: str = "auto"
    #: Scanners de rede (eSCL) digitados pelo usuario: IP, nome ou URL.
    enderecos_escl: list = field(default_factory=list)

    def validar(self) -> "Configuracao":
        padrao = Configuracao()
        if self.origem not in ORIGENS:
            self.origem = padrao.origem
        if self.cor not in CORES:
            self.cor = padrao.cor
        if self.dpi not in DPIS:
            self.dpi = padrao.dpi
        if self.papel not in PAPEIS:
            self.papel = padrao.papel
        if self.formato not in FORMATOS:
            self.formato = padrao.formato
        if self.tema not in TEMAS:
            self.tema = padrao.tema
        if self.idioma not in IDIOMAS:
            self.idioma = padrao.idioma
        if not isinstance(self.ocr, bool):
            self.ocr = padrao.ocr
        if not isinstance(self.scanner_id, str):
            self.scanner_id = ""
        if not isinstance(self.pasta_saida, str):
            self.pasta_saida = ""
        if not isinstance(self.enderecos_escl, list):
            self.enderecos_escl = []
        self.enderecos_escl = [e.strip() for e in self.enderecos_escl
                               if isinstance(e, str) and e.strip()][:20]
        return self


def carregar() -> Configuracao:
    try:
        dados = json.loads(caminho_do_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Configuracao()
    if not isinstance(dados, dict):
        return Configuracao()
    conhecidos = {f.name for f in fields(Configuracao)}
    try:
        return Configuracao(**{k: v for k, v in dados.items() if k in conhecidos}).validar()
    except TypeError:
        return Configuracao()


def salvar(config: Configuracao) -> bool:
    """Grava de forma atomica. Devolve False se nao conseguiu (nao e' fatal)."""
    destino = caminho_do_arquivo()
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(dir=destino.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(config.validar()), f, ensure_ascii=False, indent=2)
            os.replace(temporario, destino)
        except BaseException:
            try:
                os.unlink(temporario)
            except OSError:
                pass
            raise
        return True
    except OSError:
        return False
