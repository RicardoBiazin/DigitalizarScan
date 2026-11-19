"""Une as saidas: PDF (com ou sem OCR) e imagens. Sem Qt, chamado de uma thread."""

from __future__ import annotations

import pathlib
from typing import Sequence

from digitalizarscan import log_interno
from digitalizarscan.i18n import t
from digitalizarscan.saida import imagens, ocr, pdf

log = log_interno.obter(__name__)


def caminhos_previstos(destino: pathlib.Path, total: int, formato: str) -> list[pathlib.Path]:
    """Arquivos que `exportar` vai criar, para o usuario confirmar a substituicao."""
    if formato == "pdf":
        return [pathlib.Path(destino).with_suffix(".pdf")]
    return imagens.nomes_de_saida(pathlib.Path(destino), total, formato)


def exportar(paginas: Sequence[pathlib.Path], destino: pathlib.Path, formato: str, dpi: int,
             usar_ocr: bool, tesseract: ocr.Tesseract | None) -> tuple[list[pathlib.Path], str]:
    """Grava e devolve (arquivos, aviso). `aviso` nao e' vazio quando o OCR falhou e o PDF
    saiu sem texto: o scan nunca se perde por causa do OCR."""
    destino = pathlib.Path(destino)
    if formato != "pdf":
        return imagens.gravar_imagens(paginas, destino, formato, dpi), ""
    alvo = destino.with_suffix(".pdf")
    aviso = ""
    if usar_ocr:
        if tesseract is None:
            aviso = t("ocr.indisponivel_aviso")
        else:
            try:
                ocr.gerar_pdf_pesquisavel(paginas, alvo, tesseract)
                return [alvo], ""
            except ocr.ErroOcr as exc:
                log.warning("OCR falhou: %s", exc)
                aviso = t("ocr.falhou_aviso", erro=exc)
    pdf.gravar_pdf(paginas, alvo, dpi)
    return [alvo], aviso
