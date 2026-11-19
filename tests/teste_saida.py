"""Saidas: PDF multipagina, JPG/PNG, nomes e gravacao atomica."""

import pathlib
import re

from PIL import Image

from ajudantes import abrir, encerrar, igual, levanta, pasta_nova, verificar

from digitalizarscan import exportar
from digitalizarscan.documento import Documento
from digitalizarscan.saida import imagens, ocr, pdf
from digitalizarscan.saida.atomico import gravar_atomico

pasta = pasta_nova()
doc = Documento(pasta / "paginas")
doc.adicionar(Image.new("RGB", (300, 400), "red"), 100)
doc.adicionar(Image.new("L", (300, 400), 128), 100)
doc.adicionar(Image.new("1", (300, 400), 1), 100)
caminhos = doc.caminhos()

# -- PDF
destino = pasta / "saida" / "teste.pdf"
pdf.gravar_pdf(caminhos, destino, 100)
dados = destino.read_bytes()
verificar(dados.startswith(b"%PDF"), "cabecalho PDF")
igual(len(re.findall(rb"/Type\s*/Page(?![s\w])", dados)), 3, "3 paginas no PDF")
# 300 px a 100 dpi = 3 pol = 216 pt; 400 px = 288 pt
verificar(re.search(rb"/MediaBox \[ 0 0 216(\.0)? 288(\.0)? \]", dados),
          "tamanho de pagina respeita o dpi")
pdf.gravar_pdf([caminhos[2]], pasta / "pb.pdf", 100)
verificar((pasta / "pb.pdf").read_bytes().startswith(b"%PDF"), "PDF so' de paginas 1-bit")
levanta(ValueError, lambda: pdf.gravar_pdf([], pasta / "vazio.pdf", 100), "PDF sem paginas")
verificar(not (pasta / "vazio.pdf").exists(), "nada gravado sem paginas")

# -- gravacao atomica: falha no meio mantem o original e nao deixa sobra
original = pasta / "intacto.pdf"
original.write_bytes(b"ORIGINAL")
try:
    with gravar_atomico(original) as tmp:
        tmp.write_bytes(b"NOVO PELA METADE")
        raise RuntimeError("queda de luz")
except RuntimeError:
    pass
igual(original.read_bytes(), b"ORIGINAL", "original intacto apos falha")
igual(sorted(p.name for p in pasta.glob(".dscan-*")), [], "sem temporario sobrando")
with gravar_atomico(original) as tmp:
    tmp.write_bytes(b"NOVO")
igual(original.read_bytes(), b"NOVO", "substitui no sucesso")

# falha real do Pillow no meio do PDF: o original continua
pdf_existente = pasta / "ja_existe.pdf"
pdf_existente.write_bytes(b"%PDF-ANTIGO")
corrompida = pasta / "corrompida.png"
corrompida.write_bytes(b"isto nao e' um png")
try:
    pdf.gravar_pdf([caminhos[0], corrompida], pdf_existente, 100)
except Exception:
    pass
igual(pdf_existente.read_bytes(), b"%PDF-ANTIGO", "PDF antigo intacto quando uma pagina esta corrompida")

# -- nomes de saida
d = pathlib.Path("C:/x/Scan.pdf")
igual(imagens.nomes_de_saida(d, 1, "jpg"), [pathlib.Path("C:/x/Scan.jpg")], "uma pagina: nome simples")
igual([p.name for p in imagens.nomes_de_saida(d, 3, "png")], ["Scan_001.png", "Scan_002.png", "Scan_003.png"],
      "varias paginas numeradas")
igual(imagens.nomes_de_saida(d, 1000, "png")[0].name, "Scan_0001.png", "largura cresce com o total")
igual(exportar.caminhos_previstos(pathlib.Path("C:/x/Scan.jpg"), 5, "pdf"), [pathlib.Path("C:/x/Scan.pdf")],
      "PDF troca a extensao")

# -- JPG / PNG
feitos = imagens.gravar_imagens(caminhos, pasta / "img" / "Scan.png", "jpg", 100)
igual([p.name for p in feitos], ["Scan_001.jpg", "Scan_002.jpg", "Scan_003.jpg"], "JPGs gravados")
igual([abrir(p).format for p in feitos], ["JPEG"] * 3, "formato JPEG (inclusive a pagina 1-bit)")
feitos = imagens.gravar_imagens(caminhos[:1], pasta / "img" / "Uma.jpg", "png", 100)
igual([p.name for p in feitos], ["Uma.png"], "pagina unica sem numero")
igual(abrir(feitos[0]).size, (300, 400), "imagem inteira")
levanta(ValueError, lambda: imagens.gravar_imagens(caminhos, pasta / "x", "gif", 100), "formato invalido")

# -- exportar: OCR indisponivel nao perde o scan
arquivos, aviso = exportar.exportar(caminhos, pasta / "semocr.pdf", "pdf", 100, True, None)
verificar(arquivos[0].is_file() and aviso, "sem Tesseract: PDF sai com aviso")
arquivos, aviso = exportar.exportar(caminhos, pasta / "plano.pdf", "pdf", 100, False, None)
verificar(arquivos[0].is_file() and not aviso, "sem OCR pedido: sem aviso")
falso = ocr.Tesseract(pasta / "nao_existe.exe", pasta, ("por",))
arquivos, aviso = exportar.exportar(caminhos, pasta / "falhou.pdf", "pdf", 100, True, falso)
verificar(arquivos[0].is_file() and "sem texto" in aviso, "Tesseract quebrado: PDF sai sem texto, com aviso")
levanta(ocr.ErroOcr, lambda: ocr.gerar_pdf_pesquisavel(caminhos, pasta / "o.pdf", falso), "OCR levanta ErroOcr")
verificar(not (pasta / "o.pdf").exists(), "OCR que falha nao deixa arquivo")
arquivos, aviso = exportar.exportar(caminhos, pasta / "tudo.png", "png", 100, True, None)
igual(len(arquivos), 3, "imagens ignoram o OCR")

doc.descartar()
encerrar()
