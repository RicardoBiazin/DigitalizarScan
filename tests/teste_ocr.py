"""OCR de verdade com o Tesseract da pasta tesseract\\ (pula se ele nao estiver la)."""

import pathlib

from ajudantes import encerrar, igual, pasta_nova, verificar

from digitalizarscan import exportar
from digitalizarscan.documento import Documento
from digitalizarscan.saida import ocr
from digitalizarscan.scanner.base import Opcoes
from digitalizarscan.scanner.falso import ScannerFalso

tesseract = ocr.localizar()
if tesseract is None:
    print("PULADO: Tesseract nao encontrado (rode ferramentas/baixar_tesseract.ps1)")
    encerrar()

import pypdf  # noqa: E402  (so' no ambiente de desenvolvimento)

verificar("por" in tesseract.idiomas and "eng" in tesseract.idiomas, "idiomas por e eng presentes")
verificar((tesseract.tessdata / "pdf.ttf").is_file(), "pdf.ttf (fonte da camada de texto) presente")

pasta = pasta_nova()
doc = Documento(pasta / "paginas")
opcoes = Opcoes("alimentador", "cor", 300, "A4")
for imagem in ScannerFalso(3).digitalizar("x", opcoes, lambda: False):
    doc.adicionar(imagem, 300)

destino = pasta / "pesquisavel.pdf"
arquivos, aviso = exportar.exportar(doc.caminhos(), destino, "pdf", 300, True, tesseract)
igual(aviso, "", "OCR sem aviso")
leitor = pypdf.PdfReader(destino)
igual(len(leitor.pages), 3, "3 paginas no PDF pesquisavel")
textos = [p.extract_text().upper() for p in leitor.pages]
for texto, esperado in zip(textos, ("RELAT", "FATURA", "CONTRATO")):
    verificar(esperado in texto, f"texto da pagina contem {esperado}: {texto!r}")
verificar(not list(pathlib.Path(pasta).glob(".dscan-*")), "sem temporarios")

# cinza e preto e branco tambem passam pelo OCR
for cor in ("cinza", "pb"):
    outro = Documento(pasta / f"p_{cor}")
    for imagem in ScannerFalso(1).digitalizar("x", Opcoes("vidro", cor, 300, "A4"), lambda: False):
        outro.adicionar(imagem, 300)
    alvo = pasta / f"{cor}.pdf"
    exportar.exportar(outro.caminhos(), alvo, "pdf", 300, True, tesseract)
    verificar("RELAT" in pypdf.PdfReader(alvo).pages[0].extract_text().upper(), f"OCR em {cor}")
    outro.descartar()

doc.descartar()
encerrar()
