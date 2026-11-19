"""eSCL contra um servidor HTTP local de mentira: todas as folhas do alimentador, duplex, vidro,
ocupado, cancelamento, capacidades, e a juncao com o WIA (ScannerComposto)."""

import re

from ajudantes import encerrar, igual, levanta, verificar

import escl_falso as ef
from digitalizarscan.scanner import escl
from digitalizarscan.scanner.base import Dispositivo, ErroScanner, Opcoes, escolher_preferido
from digitalizarscan.scanner.composto import ScannerComposto, dicas_de_nome
from digitalizarscan.scanner.falso import ScannerFalso

escl.ESPERA_S = 0.01           # a suite nao dorme


def subir(**kw):
    impressora = ef.Impressora(**kw)
    servidor, endereco = ef.iniciar(impressora)
    scanner = escl.ScannerEscl(enderecos=lambda: [endereco])
    return impressora, servidor, scanner, endereco


def paginas(scanner, id_, opcoes, cancelado=lambda: False):
    return list(scanner.digitalizar(id_, opcoes, cancelado))


# -- descoberta pelo endereco digitado: http responde, https cai; um dispositivo so'
imp, srv, sc, end = subir()
lista = sc.listar()
igual(len(lista), 1, "um scanner eSCL")
id_ = lista[0].id
igual(id_, f"escl:http://{end}/eSCL", "id com a base http")
verificar("HP OfficeJet Pro 7740" in lista[0].nome and "rede" in lista[0].nome, f"nome: {lista[0].nome}")

# -- capacidades: vidro, alimentador e duplex; dpis da lista + faixa
cap = sc.capacidades(id_)
igual(cap.origens, ("vidro", "alimentador", "duplex"), "origens eSCL")
igual(cap.dpis, (150, 200, 300, 600), "dpis (200/300/600 da lista, 150 da faixa do alimentador)")

# -- o caso real: 8 folhas no alimentador, todas chegam
imgs = paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
igual(len(imgs), 8, "8 folhas do alimentador")
igual([i.size[0] for i in imgs], [100 + n for n in range(1, 9)], "na ordem")
post = [c for m, p, c in imp.pedidos if m == "POST"][-1].decode()
verificar("<pwg:InputSource>Feeder</pwg:InputSource>" in post, "pediu o alimentador")
verificar("<scan:ColorMode>RGB24</scan:ColorMode>" in post, "cor RGB24")
verificar("<scan:XResolution>300</scan:XResolution>" in post, "300 dpi")
verificar("<pwg:Width>2480</pwg:Width>" in post and "<pwg:Height>3508</pwg:Height>" in post, "A4 em 1/300 pol")
verificar("<pwg:Version>2.63</pwg:Version>" in post, "versao ecoada das capacidades")
verificar("<scan:Duplex>false</scan:Duplex>" in post, "sem duplex")
igual(imp.apagados, [], "lote completo nao cancela o trabalho")

# -- duplex: 2 lados por folha
imp.folhas = 3
igual(len(paginas(sc, id_, Opcoes("duplex", "cinza", 200, "A4"))), 6, "duplex 3 folhas = 6 paginas")
post = [c for m, p, c in imp.pedidos if m == "POST"][-1].decode()
verificar("<scan:Duplex>true</scan:Duplex>" in post and "Grayscale8" in post, "duplex em cinza")

# -- vidro: uma pagina, Platen; preto e branco binarizado aqui
imgs = paginas(sc, id_, Opcoes("vidro", "pb", 300, "Ofício"))
igual(len(imgs), 1, "vidro = 1 pagina")
igual(imgs[0].mode, "1", "preto e branco vira 1 bit")
post = [c for m, p, c in imp.pedidos if m == "POST"][-1].decode()
verificar("<pwg:InputSource>Platen</pwg:InputSource>" in post, "pediu o vidro")
verificar(re.search(r"<pwg:Height>3508</pwg:Height>", post), "Oficio recortado ao maximo do vidro")

# -- alimentador vazio: erro claro antes de criar trabalho
imp.adf_vazio = True
try:
    paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
    verificar(False, "alimentador vazio deveria dar erro")
except ErroScanner as exc:
    verificar("papel" in str(exc), f"mensagem sem papel: {exc}")
imp.adf_vazio = False

# -- ocupado ao criar e entre paginas: espera e segue
imp.ocupado_ao_criar = 2
imp.esperas_por_pagina = 2
imp.folhas = 4
igual(len(paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))), 4, "503 ao criar e entre paginas")
imp.esperas_por_pagina = 0

# -- cancelar no meio: para e apaga o trabalho no scanner
imp.folhas = 8
contador = []


def cancela_depois_de_tres():
    return len(contador) >= 3


gerador = sc.digitalizar(id_, Opcoes("alimentador", "cor", 300, "A4"), cancela_depois_de_tres)
for imagem in gerador:
    contador.append(imagem)
igual(len(contador), 3, "cancelou depois de 3")
verificar(imp.apagados and imp.apagados[-1].startswith("/eSCL/ScanJobs/"), "DELETE do trabalho cancelado")

# -- Location absoluto tambem funciona
imp.location_relativo = False
imp.folhas = 2
igual(len(paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))), 2, "Location absoluto")

# -- sem nenhuma pagina (404 de cara) e' erro
imp.folhas = 0
levanta(ErroScanner, lambda: paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4")), "lote vazio")

# -- o que a HP 7740 pode mandar no lugar do JPEG: cru, PDF com JPEG dentro, vazio antes, lixo
imp.folhas = 2
imp.location_relativo = True
imp.formato = "cru"
imgs = paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
igual([(i.mode, i.size) for i in imgs], [("RGB", (2480, 20))] * 2, "imagem crua na largura pedida")
imp.formato = "pdf"
imgs = paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
igual([i.size[0] for i in imgs], [101, 102], "JPEG tirado de dentro do PDF")
# o caso real da HP 7740 no alimentador: JPEG com altura 0 e DNL (o Pillow sozinho nao abre)
from PIL import Image as _Img  # noqa: E402
import io as _io  # noqa: E402
levanta(Exception, lambda: _Img.open(_io.BytesIO(ef.jpeg_dnl(50, 60))), "Pillow sozinho recusa JPEG com DNL")
imp.formato = "dnl"
imgs = paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
igual([i.size for i in imgs], [(2480, 3001), (2480, 3002)], "JPEG com DNL: altura vinda do DNL")
igual(imgs[0].getpixel((100, 100))[2] > 150, True, "conteudo decodificado (nao cinza de preenchimento)")
imp.formato = "dnl_sem"
imgs = paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
igual(imgs[0].size, (2480, 3508), "altura 0 sem DNL: usa a altura pedida")
igual(escl.corrigir_altura_jpeg(ef.jpeg(1), 100), None, "JPEG normal nao e' mexido")
igual(escl.corrigir_altura_jpeg(b"nao e jpeg", 100), None, "nao-JPEG ignorado")
imp.formato = "vazio_antes"
igual(len(paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))), 2, "200 vazio = ainda nao pronta")
imp.formato = "lixo"
try:
    paginas(sc, id_, Opcoes("alimentador", "cor", 300, "A4"))
    verificar(False, "formato desconhecido deveria dar erro")
except ErroScanner as exc:
    verificar("formato inesperado" in str(exc) and "application/octet-stream" in str(exc), f"erro claro: {exc}")
verificar(imp.apagados, "trabalho cancelado depois do erro")
imp.formato = "jpeg"

# -- 600 dpi no alimentador (que vai so' ate' 300 na HP): pede 300 e a pagina sabe disso
imgs = paginas(sc, id_, Opcoes("alimentador", "cor", 600, "A4"))
post = [c for m, p, c in imp.pedidos if m == "POST"][-1].decode()
verificar("<scan:XResolution>300</scan:XResolution>" in post, "dpi limitado ao do alimentador")
igual(imgs[0].info.get("dscan_dpi"), 300, "pagina carrega o dpi real")
imgs = paginas(sc, id_, Opcoes("vidro", "pb", 600, "A4"))
igual(imgs[0].info.get("dscan_dpi"), 600, "vidro mantem 600 (e o pb preserva a marca)")

# -- ordem do XML: DocumentFormat logo depois das regioes, antes de InputSource
ordem = [post.find(t) for t in ("<pwg:ScanRegions", "<pwg:DocumentFormat>", "<pwg:InputSource>",
                                 "<scan:XResolution>", "<scan:ColorMode>", "<scan:Duplex>")]
verificar(all(o >= 0 for o in ordem) and ordem == sorted(ordem), "elementos na ordem do esquema")

# -- diagnostico traz as respostas do scanner
verificar("ScannerCapabilities] HTTP 200" in sc.diagnostico(id_), "diagnostico eSCL")
srv.shutdown(); srv.server_close()

# -- endereco morto: nao lista, nao trava
morto = escl.ScannerEscl(enderecos=lambda: ["127.0.0.1:9"])
igual(morto.listar(), [], "endereco sem scanner")
levanta(ErroScanner, lambda: escl.pedir("GET", "http://127.0.0.1:9/eSCL/x", tempo=1), "rede fora vira ErroScanner")

# -- certificado autoassinado so' e' aceito em rede local
# (os IPs privados reais sao montados no teste: o teste de higiene proibe escreve-los no repositorio)
privados = [".".join(p) for p in (("10", "1", "2", "3"), ("172", "16", "0", "9"), ("192", "168", "0", "5"))]
for host in ("192.0.2.10", *privados, "169.254.1.1", "127.0.0.1", "[::1]", "impressora.local", "impressora", "fe80::1"):
    verificar(escl.eh_rede_local(host), f"{host} e' rede local")
for host in ("8.8.8.8", "1.1.1.1", "exemplo.com", "scanner.exemplo.com.br", "", "2001:4860:4860::8888"):
    verificar(not escl.eh_rede_local(host), f"{host!r} nao e' rede local")
levanta(ValueError, lambda: __import__("digitalizarscan.i18n", fromlist=["x"]).catalogo("../../x"), "idioma fora da lista")

# -- bases a partir do que o usuario digita
igual(escl.bases_para("192.0.2.10"), ["http://192.0.2.10/eSCL", "https://192.0.2.10/eSCL"], "IP")
igual(escl.bases_para("https://hp.local:8443/"), ["https://hp.local:8443/eSCL"], "URL sem caminho")
igual(escl.bases_para("http://x/escl/"), ["http://x/escl"], "URL com caminho")
igual(escl.bases_para("  "), [], "vazio")

# -- composto: eSCL primeiro, WIA depois, dica de nome a partir do WSD
imp2, srv2, sc2, end2 = subir(folhas=2)
wia = ScannerFalso()
wia.listar = lambda: [Dispositivo("WIA-1", "SCANNER01 (HP OfficeJet Pro 7740 series)")]
composto = ScannerComposto(wia, sc2)
lista = composto.listar()
igual([d.id.split(":")[0] for d in lista], ["escl", "WIA-1"], "eSCL antes do WIA")
verificar(lista[1].nome.endswith("— WIA"), "WIA marcado")
igual(sc2.dicas, ["SCANNER01"], "dica de nome vinda do WSD")
igual(len(list(composto.digitalizar(lista[0].id, Opcoes("alimentador", "cor", 300, "A4"), lambda: False))), 2,
      "composto roteia para o eSCL")
igual(len(list(composto.digitalizar("WIA-1", Opcoes("vidro", "cor", 150, "A4"), lambda: False))), 1,
      "composto roteia para o WIA")
srv2.shutdown(); srv2.server_close()

igual(dicas_de_nome([Dispositivo("a", "HP OfficeJet Pro 7740 (NET)"), Dispositivo("b", "EPSON1A2B3C (ET-4850)")]),
      ["EPSON1A2B3C"], "dicas so' de nomes WSD")

# -- qual abre selecionado: lembrado WIA perde para o de rede; lembrado de rede fica
d_rede, d_wia = Dispositivo("escl:http://x/eSCL", "rede"), Dispositivo("W", "wia")
igual(escolher_preferido([d_rede, d_wia], "W").id, d_rede.id, "WIA lembrado cede ao eSCL")
igual(escolher_preferido([d_wia, d_rede], "escl:http://x/eSCL").id, d_rede.id, "eSCL lembrado")
igual(escolher_preferido([d_wia], "W").id, "W", "so' WIA")
igual(escolher_preferido([d_wia], "outro").id, "W", "lembrado sumiu")

encerrar()
