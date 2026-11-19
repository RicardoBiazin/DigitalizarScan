"""Janela principal com o scanner de mentira, sem mostrar nada na tela (Qt offscreen)."""

import os
import pathlib
import time

from ajudantes import abrir, encerrar, igual, pasta_nova, verificar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from digitalizarscan import configuracao
from digitalizarscan.interface.janela_principal import JanelaPrincipal
from digitalizarscan.scanner.base import Opcoes
from digitalizarscan.scanner.falso import ScannerFalso

app = QApplication([])
JanelaPrincipal.INTERVALO_ESTADO_MS = 0     # a suite chama _sondar_estado() quando quer


class Janela(JanelaPrincipal):
    """Troca os dialogos por respostas programadas."""

    def __init__(self, *a, **kw):
        self.destino = None
        self.endereco = None
        self.respostas = []          # fila de respostas para _confirmar
        self.avisos = []
        self.salvos = []
        super().__init__(*a, **kw)

    def _avisar(self, titulo, texto):
        self.avisos.append((titulo, texto))

    def _informar(self, titulo, texto):
        self.avisos.append((titulo, texto))

    def _confirmar(self, titulo, texto):
        self.avisos.append((titulo, texto))
        return self.respostas.pop(0) if self.respostas else False

    def _pedir_endereco(self):
        return self.endereco

    def _pedir_destino(self, sugestao, formato):
        self.sugestao = sugestao
        return self.destino

    def _depois_de_salvar(self, arquivos, aviso):
        self.salvos.append((arquivos, aviso))


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


def abrir_janela(scanner=None, config=None):
    j = Janela(scanner or ScannerFalso(folhas_no_alimentador=3), config or configuracao.Configuracao(),
               documento=None)
    j._tesseract = None          # a suite da janela nao depende do OCR
    j._aplicar_config()
    j.show()
    j.atualizar_scanners()
    esperar(j, lambda: ocioso(j))
    return j


def escolher(caixa, valor):
    caixa.setCurrentIndex(caixa.findData(valor))


pasta = pasta_nova()

# -- abertura: lista scanners, preenche origens e resolucoes
j = abrir_janela()
igual(j.combo_scanner.count(), 1, "um scanner listado")
igual([j.combo_origem.itemData(i) for i in range(j.combo_origem.count())],
      ["vidro", "alimentador", "duplex"], "origens do scanner")
verificar(j.botao_digitalizar.isEnabled(), "Digitalizar habilitado")
verificar(not j.botao_salvar.isEnabled(), "Salvar desabilitado sem paginas")
verificar(not j.botao_excluir.isEnabled(), "Excluir desabilitado sem selecao")

# -- digitalizar do vidro: 1 pagina
escolher(j.combo_dpi, 150)
j.digitalizar()
verificar(esperar(j, lambda: ocioso(j) and len(j._documento) == 1), "vidro entrega 1 pagina")
igual(j.lista.count(), 1, "miniatura na lista")
igual(j.lista.item(0).text(), "Página 1", "rotulo da pagina")
verificar(j.botao_salvar.isEnabled(), "Salvar habilitado")
igual(j._documento.paginas[0].dpi, 150, "dpi da pagina")

# -- alimentador: acrescenta 3 (total 4)
escolher(j.combo_origem, "alimentador")
j.digitalizar()
verificar(esperar(j, lambda: ocioso(j) and len(j._documento) == 4), "alimentador acrescenta 3")
igual([j.lista.item(i).text() for i in range(4)], [f"Página {i}" for i in range(1, 5)], "numeracao")
igual(j.statusBar().currentMessage(), "3 página(s) digitalizada(s).", "mensagem de status")

# -- selecionar, girar
ids = [p.id for p in j._documento.paginas]
j.lista.setCurrentRow(0)
j.lista.item(0).setSelected(True)
antes = abrir(j._documento.paginas[0].caminho).size
j.girar_selecionadas(90)
igual(abrir(j._documento.paginas[0].caminho).size, antes[::-1], "girou a pagina selecionada")
igual(abrir(j._documento.paginas[1].caminho).size, antes, "outras paginas intactas")

# -- mover para a direita
j.lista.setCurrentRow(0)
verificar(j.botao_direita.isEnabled() and not j.botao_esquerda.isEnabled(), "primeira pagina so' vai para a direita")
j.mover_selecionada(1)
igual([p.id for p in j._documento.paginas], [ids[1], ids[0], ids[2], ids[3]], "Documento acompanha a lista")
igual(j.lista.currentRow(), 1, "selecao acompanha o item")
j.mover_selecionada(-1)
igual([p.id for p in j._documento.paginas], ids, "volta")
j.mover_selecionada(-1)
igual([p.id for p in j._documento.paginas], ids, "nao passa do inicio")

# -- reordenar por arraste = mexer na lista; _sincronizar_ordem traz o Documento
item = j.lista.takeItem(3)
j.lista.insertItem(0, item)
j._sincronizar_ordem()
igual([p.id for p in j._documento.paginas], [ids[3], ids[0], ids[1], ids[2]], "ordem apos arraste")
igual(j.lista.item(0).text(), "Página 1", "renumerou")

# -- excluir selecionadas
j.lista.clearSelection()
j.lista.item(0).setSelected(True)
j.lista.item(1).setSelected(True)
j.excluir_selecionadas()
igual(len(j._documento), 2, "excluiu 2")
igual(j.lista.count(), 2, "lista acompanha")
igual([p.id for p in j._documento.paginas], [ids[1], ids[2]], "sobraram as certas")

# -- salvar PDF: pede destino, grava, avisa
j.destino = pasta / "meu.pdf"
j.salvar()
verificar(esperar(j, lambda: ocioso(j) and j.salvos), "salvou")
arquivos, aviso = j.salvos[-1]
verificar(arquivos[0].read_bytes().startswith(b"%PDF"), "PDF gravado")
igual(aviso, "", "sem aviso")
verificar(j._salvo, "marcado como salvo")
igual(configuracao.carregar().pasta_saida, str(pasta), "pasta lembrada")
verificar(j.sugestao.suffix == ".pdf" and j.sugestao.name.startswith("Digitalização "), "nome sugerido")

# -- sem Tesseract a caixa vem desmarcada e desabilitada; a preferencia (ocr=True) nao se perde
verificar(not j.caixa_ocr.isChecked() and not j.caixa_ocr.isEnabled(), "OCR desmarcado sem Tesseract")
j._guardar_config()
verificar(configuracao.carregar().ocr, "preferencia de OCR preservada")
# -- OCR pedido a forca sem Tesseract: PDF sai com aviso
j.caixa_ocr.setChecked(True)
verificar(not j.caixa_ocr.isEnabled(), "OCR desabilitado sem Tesseract")
j.destino = pasta / "semocr.pdf"
j.salvar()
verificar(esperar(j, lambda: ocioso(j) and len(j.salvos) == 2), "salvou de novo")
verificar("sem texto" in j.salvos[-1][1], "aviso de OCR indisponivel")

# -- salvar JPG: nomes numerados; pergunta antes de substituir
escolher(j.combo_formato, "jpg")
j.destino = pasta / "foto.jpg"
j.salvar()
verificar(esperar(j, lambda: ocioso(j) and len(j.salvos) == 3), "salvou JPGs")
igual(sorted(p.name for p in pasta.glob("foto_*.jpg")), ["foto_001.jpg", "foto_002.jpg"], "JPGs numerados")
j.avisos.clear()
j.respostas = [False]
j.salvar()
esperar(j, lambda: ocioso(j))
igual(len(j.salvos), 3, "recusou substituir: nada gravado de novo")
verificar(any("Substituir" in t for t, _ in j.avisos), "perguntou antes de substituir")
j.respostas = [True]
j.salvar()
verificar(esperar(j, lambda: ocioso(j) and len(j.salvos) == 4), "aceitou substituir")

# -- cancelar o dialogo de salvar nao grava nada
antes = len(j.salvos)
j.destino = None
j.salvar()
esperar(j, lambda: ocioso(j))
igual(len(j.salvos), antes, "dialogo cancelado")

# -- limpar tudo pergunta se ha' pagina nao salva
j.excluir_selecionadas()          # nada selecionado: no-op
j._salvo = False
j.respostas = [False]
j.limpar_tudo()
igual(len(j._documento), 2, "recusou descartar")
j.respostas = [True]
j.limpar_tudo()
igual((len(j._documento), j.lista.count()), (0, 0), "limpou")

# -- diagnostico: grava o arquivo para suporte
j.avisos.clear()
j.diagnosticar()
verificar(esperar(j, lambda: ocioso(j) and j.avisos), "diagnostico gerado")
verificar("diagnostico.txt" in j.avisos[-1][1], "mostra onde o diagnostico foi salvo")

# -- adicionar scanner pelo endereco: grava na preferencia e atualiza a lista
j.endereco = "192.0.2.10"
j.adicionar_endereco()
esperar(j, lambda: ocioso(j))
igual(configuracao.carregar().enderecos_escl, ["192.0.2.10"], "endereco gravado")
j.adicionar_endereco()
esperar(j, lambda: ocioso(j))
igual(configuracao.carregar().enderecos_escl, ["192.0.2.10"], "sem duplicar")
j.endereco = "192.0 2.10"
j.avisos.clear()
j.adicionar_endereco()
verificar(j.avisos and "inválido" in j.avisos[-1][0], "endereco com espaco recusado")

# -- falha do scanner vira aviso, nao excecao
ruim = abrir_janela(ScannerFalso(erro="Papel atolado no scanner."))
ruim.digitalizar()
verificar(esperar(ruim, lambda: ocioso(ruim) and ruim.avisos), "aviso de falha")
verificar("atolado" in ruim.avisos[-1][1], "mensagem do scanner chega ao usuario")
igual(len(ruim._documento), 0, "nada entrou")
ruim.close()

# -- sem scanner: avisa e desabilita
class Vazio(ScannerFalso):
    def listar(self):
        return []

vazio = abrir_janela(Vazio())
verificar(not vazio.botao_digitalizar.isEnabled(), "sem scanner nao digitaliza")
verificar("Nenhum scanner" in vazio.rotulo_aviso.text(), "aviso de sem scanner")
vazio.close()

# -- preferencias: opcoes escolhidas sao gravadas e restauradas
escolher(j.combo_cor, "pb")
escolher(j.combo_papel, "Carta")
j._guardar_config()
c = configuracao.carregar()
igual((c.cor, c.papel, c.formato), ("pb", "Carta", "jpg"), "preferencias gravadas")
j2 = abrir_janela(config=configuracao.carregar())
igual((j2.combo_cor.currentData(), j2.combo_papel.currentData(), j2.combo_formato.currentData()),
      ("pb", "Carta", "jpg"), "preferencias restauradas")
j2.close()

# -- opcoes que a janela passa ao scanner
verificar(isinstance(j._opcoes(), Opcoes), "opcoes tipadas")

# -- fechar: com pagina nao salva pergunta; recusar mantem aberta
j.digitalizar()
esperar(j, lambda: ocioso(j) and len(j._documento) >= 1)
j.respostas = [False]
j.close()
verificar(j.isVisible(), "recusar sair mantem a janela")
j.respostas = [True]
j.close()
verificar(not j.isVisible(), "janela fecha")
verificar(not j._documento.pasta.exists(), "paginas temporarias apagadas ao fechar")

encerrar()
