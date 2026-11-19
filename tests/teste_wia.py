"""ScannerWia contra um COM de mentira: propriedades, alimentador, erros e cancelamento."""

from ajudantes import encerrar, igual, levanta, verificar

import com_falso as cf
from digitalizarscan.scanner import wia
from digitalizarscan.scanner.base import ErroScanner, Opcoes


wia.ESPERA_S = 0          # a suite nao dorme


def montar(folhas=1, capacidades=7, **kw):
    item = cf.Item(folhas=folhas, **kw)
    dev = cf.Dispositivo(item, capacidades=capacidades)
    scanner = wia.ScannerWia(cf.fabrica_para(cf.Info("ID1", "HP Teste", dev),
                                             cf.Info("CAM", "Camera", dev, tipo=2)))
    return scanner, item, dev


def paginas(scanner, opcoes, cancelado=lambda: False):
    return list(scanner.digitalizar("ID1", opcoes, cancelado))


# -- listar: so' scanners (Type 1), nao a camera
s, item, dev = montar()
igual([(d.id, d.nome) for d in s.listar()], [("ID1", "HP Teste")], "lista so' scanners")

# -- capacidades: bits 1 (alimentador) + 2 (vidro) + 4 (duplex)
igual(s.capacidades("ID1").origens, ("vidro", "alimentador", "duplex"), "origens com duplex")
igual(s.capacidades("ID1").dpis, (150, 300), "dpi restrito pela lista do driver")
s2, _, _ = montar(capacidades=2)
igual(s2.capacidades("ID1").origens, ("vidro",), "so' vidro")
s3, _, _ = montar(capacidades=1 | 4)
igual(s3.capacidades("ID1").origens, ("alimentador", "duplex"), "alimentador e duplex sem vidro")
levanta(ErroScanner, lambda: s.capacidades("outro"), "scanner que sumiu")

# -- vidro: uma pagina, propriedades gravadas
s, item, dev = montar(folhas=5)
imgs = paginas(s, Opcoes("vidro", "cinza", 300, "A4"))
igual(len(imgs), 1, "vidro entrega uma pagina so'")
igual(item.prop(6146)._valor, 2, "cinza = intencao 2")
igual(item.prop(6147)._valor, 300, "dpi x")
igual(item.prop(6148)._valor, 300, "dpi y")
igual(item.prop(6151)._valor, round(210 / 25.4 * 300), "largura A4 em pixels")
igual(item.prop(6152)._valor, min(round(297 / 25.4 * 300), int(11.69 * 300)), "altura A4 em pixels (limitada ao vidro)")
igual(item.prop(3088)._valor, 2, "origem vidro")
igual(item.prop(3096)._valor, 1, "1 pagina no vidro")

# -- area total e limite do vidro (8,5 x 11,69 pol)
paginas(s, Opcoes("vidro", "cor", 150, "total"))
igual(item.prop(6151)._valor, int(8.5 * 150), "area total = vidro")
s, item, dev = montar(folhas=2)
paginas(s, Opcoes("vidro", "cor", 150, "Ofício"))
igual(item.prop(6152)._valor, int(11.69 * 150), "Oficio recortado ao tamanho do vidro")

# -- alimentador: le ate' faltar papel e termina sem erro
s, item, dev = montar(folhas=3)
igual(len(paginas(s, Opcoes("alimentador", "cor", 150, "A4"))), 3, "3 folhas")
igual(item.prop(3088)._valor, 1, "origem alimentador")
igual(item.prop(3096)._valor, 1, "uma folha por transferencia")

s, item, dev = montar(folhas=2)
paginas(s, Opcoes("duplex", "cor", 150, "A4"))
igual(item.prop(3088)._valor, 1 | 4, "origem duplex")

# -- alimentador vazio: erro claro, nao lote vazio mudo
s, item, dev = montar(folhas=0)
try:
    paginas(s, Opcoes("alimentador", "cor", 150, "A4"))
    verificar(False, "alimentador vazio deveria dar erro")
except ErroScanner as exc:
    verificar("papel" in str(exc).lower(), f"mensagem do alimentador vazio: {exc}")

# -- cancelar no meio
s, item, dev = montar(folhas=10)
chamadas = []


def cancela_na_terceira():
    chamadas.append(1)
    return len(chamadas) > 3


igual(len(paginas(s, Opcoes("alimentador", "cor", 150, "A4"), cancela_na_terceira)), 3, "cancelamento")

# -- PNG recusado: cai para BMP
s, item, dev = montar(folhas=1, falha_png=True)
igual(len(paginas(s, Opcoes("vidro", "cor", 150, "A4"))), 1, "fallback de formato")
igual(item.formatos, [wia.FORMATO_PNG, wia.FORMATO_BMP], "tentou PNG e depois BMP")

# -- propriedade que o driver recusa nao derruba
s, item, dev = montar(folhas=1, propriedades=[cf.Propriedade(6147, 150, recusa=True)])
igual(len(paginas(s, Opcoes("vidro", "cor", 150, "A4"))), 1, "driver recusa propriedades")

# -- erros do dispositivo viram mensagem em portugues
s, item, dev = montar(erro_inicial=cf.OCUPADO)
try:
    paginas(s, Opcoes("vidro", "cor", 150, "A4"))
    verificar(False, "scanner ocupado deveria dar erro")
except ErroScanner as exc:
    verificar("ocupado" in str(exc), f"mensagem de ocupado: {exc}")
s = wia.ScannerWia(cf.fabrica_para(erro=cf.COMUNICACAO))
levanta(ErroScanner, s.listar, "sem comunicacao")
try:
    s.listar()
except ErroScanner as exc:
    verificar("comunicação" in str(exc), f"mensagem de comunicacao: {exc}")

# -- codigo do erro: excepinfo manda; DISP_E_EXCEPTION sozinho nao e' o codigo do WIA
igual(wia.codigo_do_erro(cf.erro_com(cf.SEM_PAPEL)), 0x80210003, "scode do excepinfo")
igual(wia.codigo_do_erro(ValueError("x")), None, "excecao qualquer")
verificar("0x80210099" in str(wia.erro_amigavel(cf.erro_com(0x80210099 - (1 << 32)))),
          "codigo desconhecido aparece")

# -- WIA 2.0 (caso da HP 7740 por WSD): itens filhos Flatbed e Feeder; origem pelo item certo
def montar2(folhas_adf=2, **kw_adf):
    vidro = cf.Item(folhas=1, categoria=cf.CAT_VIDRO, nome="Flatbed")
    adf = cf.Item(folhas=folhas_adf, categoria=cf.CAT_ALIMENTADOR, nome="Feeder", capacidades=1 | 4, **kw_adf)
    dev = cf.Dispositivo([vidro, adf], capacidades=0)
    return wia.ScannerWia(cf.fabrica_para(cf.Info("ID1", "HP WSD", dev))), vidro, adf


s, vidro, adf = montar2()
igual(s.capacidades("ID1").origens, ("vidro", "alimentador", "duplex"), "WIA 2.0: origens pelos itens")
igual(len(paginas(s, Opcoes("alimentador", "cor", 300, "A4"))), 2, "WIA 2.0: alimentador usa o item Feeder")
igual((vidro.formatos, len(adf.formatos) > 0), ([], True), "nao tocou no item do vidro")
igual(adf.prop(3088)._valor, 1, "origem gravada no item do alimentador")
s, vidro, adf = montar2()
igual(len(paginas(s, Opcoes("vidro", "cor", 300, "A4"))), 1, "WIA 2.0: vidro usa o item Flatbed")
igual(adf.formatos, [], "nao tocou no alimentador")
s, vidro, adf = montar2()
paginas(s, Opcoes("duplex", "cor", 300, "A4"))
igual(adf.prop(3088)._valor, 1 | 4, "duplex no item do alimentador")

# so' por nome (sem GUID de categoria)
adf2 = cf.Item(folhas=1, nome="Feeder")
vid2 = cf.Item(folhas=1, nome="Flatbed")
s = wia.ScannerWia(cf.fabrica_para(cf.Info("ID1", "HP", cf.Dispositivo([vid2, adf2]))))
paginas(s, Opcoes("alimentador", "cor", 300, "A4"))
igual((len(vid2.formatos), len(adf2.formatos) > 0), (0, True), "item escolhido pelo nome")

# E_INVALIDARG na 1a pagina: repete so' com origem, cor e dpi
s, vidro, adf = montar2(folhas_adf=2, exige_minimo=True)
try:
    imgs = paginas(s, Opcoes("alimentador", "cor", 300, "A4"))
    igual(len(imgs), 2, "segunda tentativa minima entrega as paginas")
except ErroScanner as exc:
    verificar(False, f"deveria ter se recuperado do argumento invalido: {exc}")

# driver que so' aceita alimentador + SO_FRENTE (33): a variante 1 resolve
s, item, dev = montar(folhas=2, exige_origem=33)
igual(len(paginas(s, Opcoes("alimentador", "cor", 300, "A4"))), 2, "variante com SO_FRENTE")
s, item, dev = montar(folhas=1, exige_origem=999)
levanta(ErroScanner, lambda: paginas(s, Opcoes("alimentador", "cor", 300, "A4")), "esgota as variantes e avisa")

# scanner ocupado: espera e repete, sem virar erro (job anterior terminando, folha sendo ejetada)
s, item, dev = montar(folhas=2, ocupado_vezes=3)
igual(len(paginas(s, Opcoes("alimentador", "cor", 300, "A4"))), 2, "ocupado 3 vezes e depois digitaliza")
s, item, dev = montar(folhas=1, ocupado_vezes=wia.ESPERAS_MAXIMAS + 5)
try:
    paginas(s, Opcoes("vidro", "cor", 300, "A4"))
    verificar(False, "ocupado para sempre deveria desistir")
except ErroScanner as exc:
    verificar("ocupado" in str(exc), f"desiste com mensagem de ocupado: {exc}")
igual(item.ocupado_vezes, 4, "esperou so' ESPERAS_MAXIMAS vezes (+1 tentativa final)")

# WSD: depois da ultima folha o driver responde "ocupado" em vez de "sem papel" -> fim do lote, sem erro
s, item, dev = montar(folhas=2, fim_ocupado=True)
igual(len(paginas(s, Opcoes("alimentador", "cor", 300, "A4"))), 2, "ocupado apos a ultima folha encerra o lote")
s, item, dev = montar(folhas=0, fim_ocupado=True)
try:
    paginas(s, Opcoes("alimentador", "cor", 300, "A4"))
    verificar(False, "ocupado sem nenhuma pagina deveria ser erro")
except ErroScanner as exc:
    verificar("ocupado" in str(exc), f"erro de ocupado sem paginas: {exc}")

# diagnostico lista dispositivo e itens
s, vidro, adf = montar2()
texto = s.diagnostico("ID1")
verificar("item 1: vidro" in texto and "item 2: alimentador" in texto and "3088" in texto, "diagnostico completo")

encerrar()
