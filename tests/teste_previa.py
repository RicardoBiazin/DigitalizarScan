"""Previa do vidro com recorte de area e deteccao de papel no alimentador."""

import re
import time

from PIL import Image

from ajudantes import abrir, encerrar, igual, levanta, verificar

import com_falso as cf
import escl_falso as ef
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from digitalizarscan import configuracao
from digitalizarscan.interface import dialogo_previa as dp
from digitalizarscan.interface.janela_principal import JanelaPrincipal
from digitalizarscan.scanner import escl, wia
from digitalizarscan.scanner.base import Dispositivo, ErroScanner, EstadoScanner, Opcoes
from digitalizarscan.scanner.composto import ScannerComposto
from digitalizarscan.scanner.falso import VIDRO_MM, ScannerFalso

escl.ESPERA_S = 0.01
wia.ESPERA_S = 0

# -- selecao_para_mm: regra de tres da imagem exibida para os mm do vidro
vidro = (216.0, 297.0)
igual(dp.selecao_para_mm((10, 20, 60, 70), (108, 148.5), vidro), (20.0, 40.0, 100.0, 100.0), "canto sup. esq. -> mm")
igual(dp.selecao_para_mm((60, 70, 10, 20), (108, 148.5), vidro), (20.0, 40.0, 100.0, 100.0), "cantos invertidos")
igual(dp.selecao_para_mm((-30, -30, 54, 74.25), (108, 148.5), vidro), (0.0, 0.0, 108.0, 148.5), "recorta ao que esta' dentro")
igual(dp.selecao_para_mm((0, 0, 108, 148.5), (108, 148.5), vidro), (0.0, 0.0, 216.0, 297.0), "vidro inteiro")
igual(dp.selecao_para_mm((10, 10, 12, 12), (108, 148.5), vidro), None, "area minuscula = sem selecao")
igual(dp.selecao_para_mm((200, 200, 300, 300), (108, 148.5), vidro), None, "tudo fora da imagem")
igual(dp.selecao_para_mm((10, 10, 50, 50), (0, 0), vidro), None, "imagem sem tamanho")
volta = dp.mm_para_selecao((20.0, 40.0, 100.0, 100.0), (108, 148.5), vidro)
igual(tuple(round(v, 1) for v in volta), (10.0, 20.0, 60.0, 70.0), "mm_para_selecao e' o inverso")

# -- eSCL: area em 1/300 pol, so' no vidro, recortada ao vidro
impressora = ef.Impressora()
servidor, endereco = ef.iniciar(impressora)
sc = escl.ScannerEscl(enderecos=lambda: [endereco])
id_ = sc.listar()[0].id
cap = sc.capacidades(id_)
verificar(cap.vidro_mm is not None and abs(cap.vidro_mm[0] - 215.9) < 0.2 and abs(cap.vidro_mm[1] - 297.0) < 0.2,
          f"vidro_mm vindo do Platen: {cap.vidro_mm}")
capacidade = sc._capacidade(escl.PREFIXO and id_.removeprefix(escl.PREFIXO))
pedido = escl.montar_pedido(Opcoes("vidro", "cor", 300, "total", regiao_mm=(10, 20, 100, 150)), capacidade)
igual((pedido.x, pedido.y, pedido.largura, pedido.altura), (118, 236, 1181, 1772), "mm -> 1/300 pol")
xml = escl.xml_do_trabalho(Opcoes("vidro", "cor", 300, "total", regiao_mm=(10, 20, 100, 150)), capacidade).decode()
verificar("<pwg:XOffset>118</pwg:XOffset>" in xml and "<pwg:YOffset>236</pwg:YOffset>" in xml, "offsets no XML")
verificar("<pwg:Width>1181</pwg:Width>" in xml and "<pwg:Height>1772</pwg:Height>" in xml, "tamanho no XML")
pedido = escl.montar_pedido(Opcoes("vidro", "cor", 300, "total", regiao_mm=(200, 280, 100, 100)), capacidade)
verificar(pedido.x + pedido.largura <= 2550 and pedido.y + pedido.altura <= 3508, "area recortada ao vidro")
pedido = escl.montar_pedido(Opcoes("alimentador", "cor", 300, "A4", regiao_mm=(10, 20, 100, 150)), capacidade)
igual((pedido.x, pedido.y), (0, 0), "o alimentador ignora a area")
xml = escl.xml_do_trabalho(Opcoes("vidro", "cor", 300, "A4"), capacidade).decode()
verificar("<scan:Intent>Document</scan:Intent>" in xml, "intencao padrao")

# -- eSCL: previa = Platen inteiro, 75 dpi, Intent Preview
imagem = sc.previa(id_)
post = [c for m, p, c in impressora.pedidos if m == "POST"][-1].decode()
verificar("<scan:Intent>Preview</scan:Intent>" in post, "intencao Preview")
verificar("<pwg:InputSource>Platen</pwg:InputSource>" in post, "previa no vidro")
verificar("<scan:XResolution>75</scan:XResolution>" in post, "75 dpi")
verificar("<pwg:Width>2550</pwg:Width>" in post and "<pwg:Height>3508</pwg:Height>" in post, "vidro inteiro")
verificar(isinstance(imagem, Image.Image), "previa devolve imagem")

# -- eSCL: estado do alimentador
impressora.adf_vazio = False
igual(sc.estado(id_), EstadoScanner(papel=True), "AdfLoaded -> com papel")
impressora.adf_vazio = True
igual(sc.estado(id_), EstadoScanner(papel=False), "AdfEmpty -> vazio")
servidor.shutdown()
servidor.server_close()

# -- composto: previa e estado roteados; WIA nao informa papel
wia_falso = ScannerFalso()
wia_falso.listar = lambda: [Dispositivo("WIA-1", "Scanner USB")]
imp2 = ef.Impressora()
srv2, end2 = ef.iniciar(imp2)
composto = ScannerComposto(wia_falso, escl.ScannerEscl(enderecos=lambda: [end2]))
lista = composto.listar()
igual(composto.estado("WIA-1"), EstadoScanner(papel=None), "WIA: papel desconhecido")
igual(composto.estado(lista[0].id), EstadoScanner(papel=True), "eSCL via composto")
verificar(isinstance(composto.previa(lista[0].id), Image.Image), "previa eSCL via composto")
verificar(isinstance(composto.previa("WIA-1"), Image.Image), "previa do WIA falso via composto")
srv2.shutdown()
srv2.server_close()


# -- WIA: area em pixels do dpi e vidro_mm das propriedades 3074/3075
item = cf.Item(folhas=10)
dev = cf.Dispositivo(item)
scanner_wia = wia.ScannerWia(cf.fabrica_para(cf.Info("ID1", "HP Teste", dev)))
cap_wia = scanner_wia.capacidades("ID1")
verificar(cap_wia.vidro_mm is not None and abs(cap_wia.vidro_mm[0] - 215.9) < 0.1
          and abs(cap_wia.vidro_mm[1] - 296.9) < 0.2, f"WIA vidro_mm: {cap_wia.vidro_mm}")
list(scanner_wia.digitalizar("ID1", Opcoes("vidro", "cor", 150, "total", regiao_mm=(25.4, 50.8, 76.2, 101.6)),
                             lambda: False))
igual((item.prop(6149)._valor, item.prop(6150)._valor), (150, 300), "WIA: posicao em pixels a 150 dpi")
igual((item.prop(6151)._valor, item.prop(6152)._valor), (450, 600), "WIA: tamanho em pixels a 150 dpi")
list(scanner_wia.digitalizar("ID1", Opcoes("vidro", "cor", 150, "total", regiao_mm=(0, 0, 400, 400)), lambda: False))
verificar(item.prop(6151)._valor <= int(8.5 * 150), "WIA: area maior que o vidro e' recortada")
imagem = scanner_wia.previa("ID1")
igual(item.prop(6147)._valor, 75, "WIA: previa a 75 dpi")
igual((item.prop(6151)._valor, item.prop(6152)._valor), (int(8.5 * 75), int(11.69 * 75)), "WIA: previa no vidro inteiro")

# -- scanner de mentira: area e previa
falso = ScannerFalso()
paginas = list(falso.digitalizar("x", Opcoes("vidro", "cor", 150, "total", regiao_mm=(10, 10, 50.8, 25.4)), lambda: False))
igual(paginas[0].size, (300, 150), "falso: pagina do tamanho da area (2 x 1 pol a 150 dpi)")
previa = falso.previa("x")
igual(previa.size, (round(VIDRO_MM[0] / 25.4 * 75), round(VIDRO_MM[1] / 25.4 * 75)), "falso: previa do vidro inteiro")

# -- a janela de previa (sem mostrar na tela)
app = QApplication([])
JanelaPrincipal.INTERVALO_ESTADO_MS = 0
dialogo = dp.DialogoPrevia(previa, VIDRO_MM)
verificar(not dialogo.botao_usar.isEnabled(), "sem selecao nao da' para usar")
igual(dialogo.selecao_mm(), None, "sem selecao")
largura, altura = dialogo.visor.width(), dialogo.visor.height()
dialogo.visor.definir_selecao(QRect(0, 0, largura // 2, altura // 2))
regiao = dialogo.selecao_mm()
verificar(regiao is not None and abs(regiao[0]) < 0.5 and abs(regiao[2] - VIDRO_MM[0] / 2) < 1.5
          and abs(regiao[3] - VIDRO_MM[1] / 2) < 1.5, f"selecao do quadrante: {regiao}")
verificar(dialogo.botao_usar.isEnabled(), "com selecao da' para usar")
verificar("mm" in dialogo.rotulo_selecao.text(), "rotulo mostra a area")
dialogo.botao_usar.click()
igual(dialogo.regiao_mm, regiao, "regiao devolvida ao usar")
dialogo.visor.definir_selecao(None)
verificar(not dialogo.botao_usar.isEnabled(), "limpar desabilita Usar")
reaberto = dp.DialogoPrevia(previa, VIDRO_MM, regiao_mm=(20.0, 40.0, 100.0, 100.0))
volta = reaberto.selecao_mm()
verificar(volta is not None and all(abs(a - b) < 2.5 for a, b in zip(volta, (20.0, 40.0, 100.0, 100.0))),
          f"reabre com a area anterior: {volta}")

# -- a janela principal: previa -> area -> digitalizar

class Janela(JanelaPrincipal):
    def __init__(self, *a, **kw):
        self.avisos = []
        self.resposta_previa = None
        super().__init__(*a, **kw)

    def _avisar(self, titulo, texto):
        self.avisos.append((titulo, texto))

    def _confirmar(self, titulo, texto):
        return True

    def _mostrar_previa(self, imagem):
        self.imagem_da_previa = imagem
        return self.resposta_previa


def esperar(janela, condicao, limite=15.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        app.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def ocioso(j):
    return not j._ocupado and not j._trabalhos


def escolher(caixa, valor):
    caixa.setCurrentIndex(caixa.findData(valor))


scanner = ScannerFalso()
j = Janela(scanner, configuracao.Configuracao())
j._tesseract = None
j.show()
j.atualizar_scanners()
esperar(j, lambda: ocioso(j))
verificar(j._vidro_mm == VIDRO_MM, "janela guarda o tamanho do vidro")
verificar(j.botao_previa.isEnabled(), "Previa habilitada no vidro")
escolher(j.combo_origem, "alimentador")
verificar(not j.botao_previa.isEnabled(), "Previa desabilitada no alimentador")
escolher(j.combo_origem, "vidro")
verificar(j.botao_previa.isEnabled(), "Previa volta no vidro")

j.resposta_previa = (25.4, 25.4, 50.8, 76.2)
j.abrir_previa()
verificar(esperar(j, lambda: ocioso(j) and j.combo_papel.findData("area") >= 0), "area entra no combo de papel")
igual(j.combo_papel.currentData(), "area", "area selecionada no combo")
verificar("51 × 76 mm" in j.combo_papel.currentText(), f"rotulo da area: {j.combo_papel.currentText()}")
igual(j.imagem_da_previa.size[0] > 0, True, "a janela recebeu a imagem da previa")
opcoes = j._opcoes()
igual((opcoes.papel, opcoes.regiao_mm), ("total", (25.4, 25.4, 50.8, 76.2)), "opcoes levam a area")
escolher(j.combo_dpi, 150)
j.digitalizar()
verificar(esperar(j, lambda: ocioso(j) and len(j._documento) == 1), "digitalizou a area")
igual(abrir(j._documento.paginas[0].caminho).size, (300, 450), "pagina do tamanho da area (2 x 3 pol a 150 dpi)")
igual(scanner.chamadas[-1].regiao_mm, (25.4, 25.4, 50.8, 76.2), "o scanner recebeu a area")

# escolher outro papel tira a area; mudar para o alimentador tambem
j.combo_papel.setCurrentIndex(j.combo_papel.findData("Carta"))
j.combo_papel.activated.emit(j.combo_papel.currentIndex())
igual(j.combo_papel.findData("area"), -1, "outro papel remove a area")
igual((j.combo_papel.currentData(), j._regiao_mm), ("Carta", None), "papel escolhido fica e a area some")
j._definir_regiao((10, 10, 40, 40))
igual(j.combo_papel.currentData(), "area", "area de volta")
escolher(j.combo_origem, "alimentador")
igual((j.combo_papel.findData("area"), j._regiao_mm), (-1, None), "alimentador remove a area")
igual(j.combo_papel.currentData(), "Carta", "volta ao papel de antes")
escolher(j.combo_origem, "vidro")

# a area nao vai para a preferencia (guarda o papel de antes)
j._definir_regiao((10, 10, 40, 40))
j._guardar_config()
igual(configuracao.carregar().papel, "Carta", "preferencia guarda o papel, nao a area")
j._definir_regiao(None)

# cancelar a previa nao muda nada; "atualizar" abre outra
j.resposta_previa = "cancelar"
j.abrir_previa()
esperar(j, lambda: ocioso(j))
igual(j._regiao_mm, None, "cancelar nao seleciona")
j.resposta_previa = "atualizar"
original = j.abrir_previa
contagem = []
j.abrir_previa = lambda: (contagem.append(1), setattr(j, "resposta_previa", "cancelar") if len(contagem) > 1 else None,
                          original())[-1]
j.abrir_previa()
verificar(esperar(j, lambda: len(contagem) >= 2 and ocioso(j)), "'atualizar' refaz a previa")
j.abrir_previa = original

# falha da previa vira aviso


class PreviaQuebrada(ScannerFalso):
    def previa(self, dispositivo_id):
        raise ErroScanner("Papel atolado no scanner.")


ruim = Janela(PreviaQuebrada(), configuracao.Configuracao())
ruim._tesseract = None
ruim.show()
ruim.atualizar_scanners()
esperar(ruim, lambda: ocioso(ruim))
ruim.abrir_previa()
verificar(esperar(ruim, lambda: ocioso(ruim) and ruim.avisos), "falha da previa vira aviso")
verificar("atolado" in ruim.avisos[-1][1], "mensagem do scanner chega ao usuario")
ruim._salvo = True
ruim.close()

# -- papel no alimentador: indicador e troca de origem so' na transicao
scanner.papel_no_alimentador = None
j._reiniciar_estado_do_alimentador()
escolher(j.combo_origem, "vidro")
j._sondar_estado()
esperar(j, lambda: ocioso(j))
verificar(not j.rotulo_alimentador.isVisibleTo(j), "sem informacao: indicador escondido")
igual(j.combo_origem.currentData(), "vidro", "sem informacao: origem intacta")

scanner.papel_no_alimentador = True
j._sondar_estado()
verificar(esperar(j, lambda: j.rotulo_alimentador.isVisibleTo(j)), "indicador aparece")
igual(j.rotulo_alimentador.text(), "Alimentador: com papel", "texto com papel")
igual(j.combo_origem.currentData(), "alimentador", "primeira leitura com papel escolhe o alimentador")

escolher(j.combo_origem, "vidro")                 # o usuario discorda
j._sondar_estado()
esperar(j, lambda: ocioso(j))
igual(j.combo_origem.currentData(), "vidro", "mesmo estado: a escolha manual vale")

scanner.papel_no_alimentador = False
j._sondar_estado()
esperar(j, lambda: j.rotulo_alimentador.text() == "Alimentador: vazio")
igual(j.combo_origem.currentData(), "vidro", "vazio com origem vidro: continua")
escolher(j.combo_origem, "alimentador")
scanner.papel_no_alimentador = True
j._sondar_estado()
esperar(j, lambda: j.rotulo_alimentador.text() == "Alimentador: com papel")
igual(j.combo_origem.currentData(), "alimentador", "com papel e alimentador: continua")
scanner.papel_no_alimentador = False
j._sondar_estado()
esperar(j, lambda: j.rotulo_alimentador.text() == "Alimentador: vazio")
igual(j.combo_origem.currentData(), "vidro", "papel acabou: volta para o vidro")

escolher(j.combo_origem, "duplex")
scanner.papel_no_alimentador = True
j._sondar_estado()
esperar(j, lambda: j.rotulo_alimentador.text() == "Alimentador: com papel")
igual(j.combo_origem.currentData(), "duplex", "com papel e duplex: respeita o duplex")

# nao troca no meio de uma digitalizacao nem consulta quando ocupado
j._ocupado = True
antes = j._papel_no_alimentador
scanner.papel_no_alimentador = False
j._sondar_estado()
time.sleep(0.2)
app.processEvents()
igual(j._papel_no_alimentador, antes, "ocupado: nao consulta")
j._ocupado = False

# falhas seguidas param o relogio
j.INTERVALO_ESTADO_MS = 0
j._timer_estado.start(60000)
for _ in range(3):
    j._estado_falhou("sem rede")
verificar(not j._timer_estado.isActive(), "3 falhas seguidas param a consulta")

# o indicador acompanha o idioma
j.definir_idioma("en")
igual(j.rotulo_alimentador.text(), "Feeder: empty" if j._papel_no_alimentador is False else "Feeder: paper loaded",
      "indicador traduzido")
j.definir_idioma("pt")
j._salvo = True
j.close()

encerrar()
