"""PDF pesquisavel com o Tesseract.

O Tesseract roda como processo (lista de argumentos, sem shell). Recebe um arquivo
com a lista de imagens e devolve um PDF multipagina com a camada de texto. O
binario vem na pasta "tesseract" ao lado do programa (ver
ferramentas/baixar_tesseract.ps1); se nao estiver la', procura a instalacao
padrao do Windows e depois o PATH.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Sequence

from digitalizarscan.i18n import t
from digitalizarscan.saida.atomico import gravar_atomico

#: Modelos do Tesseract por idioma da interface (o ingles entra sempre: documentos misturam).
IDIOMAS_POR_UI = {"pt": ("por", "eng"), "en": ("eng",), "es": ("spa", "eng"), "zh": ("chi_sim", "eng")}
#: Se o modelo do idioma da interface nao estiver na pasta, usa o que houver destes.
IDIOMAS_RESERVA = ("eng", "por", "spa", "chi_sim")
SEGUNDOS_POR_PAGINA = 180


class ErroOcr(Exception):
    """Falha do OCR com mensagem para o usuario."""


@dataclass(frozen=True)
class Tesseract:
    exe: pathlib.Path
    tessdata: pathlib.Path
    idiomas: tuple[str, ...]


def _pasta_do_programa() -> pathlib.Path:
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _candidatos() -> list[pathlib.Path]:
    achados = []
    forcado = os.environ.get("DIGITALIZARSCAN_TESSERACT")
    if forcado:
        achados.append(pathlib.Path(forcado))
    empacotado = getattr(sys, "_MEIPASS", "")
    if empacotado:
        achados.append(pathlib.Path(empacotado) / "tesseract" / "tesseract.exe")
    achados.append(_pasta_do_programa() / "tesseract" / "tesseract.exe")
    achados.append(pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
                   / "Tesseract-OCR" / "tesseract.exe")
    no_path = shutil.which("tesseract")
    if no_path:
        achados.append(pathlib.Path(no_path))
    return achados


def localizar(idioma_da_interface: str = "pt") -> Tesseract | None:
    """O primeiro Tesseract utilizavel, com os modelos do idioma da interface (ou o que houver)."""
    desejados = IDIOMAS_POR_UI.get(idioma_da_interface, IDIOMAS_POR_UI["en"])
    for exe in _candidatos():
        if not exe.is_file():
            continue
        tessdata = exe.parent / "tessdata"
        if not tessdata.is_dir():
            continue
        idiomas = tuple(i for i in desejados if (tessdata / f"{i}.traineddata").is_file())
        if not idiomas:
            idiomas = tuple(i for i in IDIOMAS_RESERVA if (tessdata / f"{i}.traineddata").is_file())[:2]
        if idiomas:
            return Tesseract(exe, tessdata, idiomas)
    return None


def gerar_pdf_pesquisavel(paginas: Sequence[pathlib.Path], destino: pathlib.Path,
                          tesseract: Tesseract,
                          cancelado: Callable[[], bool] = lambda: False) -> None:
    if not paginas:
        raise ValueError("nenhuma pagina para reconhecer")
    trabalho = pathlib.Path(tempfile.mkdtemp(prefix="dscan-ocr-"))
    try:
        lista = trabalho / "paginas.txt"
        lista.write_text("\n".join(str(p) for p in paginas) + "\n", encoding="utf-8")
        base = trabalho / "saida"
        ambiente = dict(os.environ, TESSDATA_PREFIX=str(tesseract.tessdata))
        comando = [str(tesseract.exe), str(lista), str(base),
                   "-l", "+".join(tesseract.idiomas), "pdf"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            resultado = subprocess.run(
                comando, env=ambiente, capture_output=True, creationflags=flags,
                timeout=SEGUNDOS_POR_PAGINA * len(paginas), check=False)
        except subprocess.TimeoutExpired as exc:
            raise ErroOcr(t("ocr.demorou")) from exc
        except OSError as exc:
            raise ErroOcr(t("ocr.nao_executou", erro=exc)) from exc
        pdf = base.with_suffix(".pdf")
        if resultado.returncode != 0 or not pdf.is_file():
            detalhe = resultado.stderr.decode("utf-8", "replace").strip().splitlines()
            if detalhe:
                raise ErroOcr(t("ocr.falhou", detalhe=detalhe[-1]))
            raise ErroOcr(t("ocr.falhou_codigo", codigo=resultado.returncode))
        if cancelado():
            raise ErroOcr(t("ocr.cancelado"))
        with gravar_atomico(destino) as temporario:
            shutil.copyfile(pdf, temporario)
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)
