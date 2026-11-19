"""Janela principal do DigitalizarScan."""

from __future__ import annotations

import datetime
import os
import pathlib
import re

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QListView, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from digitalizarscan import NOME, VERSAO, configuracao, exportar, i18n, idioma, log_interno, tema
from digitalizarscan.documento import Documento
from digitalizarscan.i18n import t
from digitalizarscan.interface.dialogo_previa import DialogoPrevia
from digitalizarscan.saida import ocr
from digitalizarscan.scanner.base import Capacidades, Opcoes, Scanner, escolher_preferido
from digitalizarscan.trabalho import (TrabalhoCapacidades, TrabalhoDigitalizar, TrabalhoEstado,
                                      TrabalhoListar, TrabalhoPrevia, TrabalhoSalvar)

log = log_interno.obter(__name__)

#: Valor guardado (configuracao / itemData) -> chave do catalogo. Os valores nao mudam com o idioma.
CHAVE_ORIGEM = {"vidro": "origem.vidro", "alimentador": "origem.alimentador", "duplex": "origem.duplex"}
CHAVE_COR = {"cor": "cor.cor", "cinza": "cor.cinza", "pb": "cor.pb"}
CHAVE_PAPEL = {"A4": "papel.A4", "Carta": "papel.Carta", "Ofício": "papel.Oficio", "total": "papel.total"}
CHAVE_FORMATO = {"pdf": "formato.pdf", "jpg": "formato.jpg", "png": "formato.png"}
CHAVE_FILTRO = {"pdf": "filtro.pdf", "jpg": "filtro.jpg", "png": "filtro.png"}
CHAVE_TEMA = {"sistema": "menu.tema.sistema", "claro": "menu.tema.claro", "escuro": "menu.tema.escuro"}

_CODIGO_HEX = re.compile(r"0x[0-9A-Fa-f]{8}")


def _combo(chaves: dict[str, str]) -> QComboBox:
    caixa = QComboBox()
    for valor, chave in chaves.items():
        caixa.addItem(t(chave), valor)
    return caixa


def _escolher(caixa: QComboBox, valor) -> None:
    indice = caixa.findData(valor)
    if indice >= 0:
        caixa.setCurrentIndex(indice)


def _retraduzir_combo(caixa: QComboBox, chaves: dict[str, str]) -> None:
    for i in range(caixa.count()):
        chave = chaves.get(caixa.itemData(i))
        if chave:
            caixa.setItemText(i, t(chave))


class JanelaPrincipal(QMainWindow):
    #: Intervalo de consulta do papel no alimentador (ms). 0 desliga (os testes desligam).
    INTERVALO_ESTADO_MS = 3000

    def __init__(self, scanner: Scanner, config: configuracao.Configuracao | None = None,
                 documento: Documento | None = None):
        super().__init__()
        self._scanner = scanner
        self._config = config or configuracao.carregar()
        self._documento = documento or Documento()
        self._tesseract = ocr.localizar(i18n.idioma_atual())
        self._trabalhos: set = set()        # referencias vivas das threads
        self._digitalizando: TrabalhoDigitalizar | None = None
        self._ocupado = False
        self._salvo = True                  # nao ha' nada a perder
        self._ultimo_salvo: list[pathlib.Path] = []
        self._tem_scanner = False
        self._novas = 0
        self._vidro_mm: tuple[float, float] | None = None
        self._regiao_mm: tuple[float, float, float, float] | None = None
        self._papel_antes_da_area = "A4"
        self._papel_no_alimentador: bool | None = None     # ultima leitura do scanner
        self._papel_ja_lido = False
        self._falhas_estado = 0
        self._sondando = False

        self.setWindowTitle(f"{NOME} {VERSAO}")
        self.resize(1000, 640)
        self.setMinimumSize(760, 460)
        icone = pathlib.Path(__file__).resolve().parent.parent / "recursos" / "icone.ico"
        if icone.is_file():
            self.setWindowIcon(QIcon(str(icone)))

        self._montar()
        self._aplicar_config()
        self._atualizar_estado()

        self._timer_estado = QTimer(self)
        self._timer_estado.timeout.connect(self._sondar_estado)
        if self.INTERVALO_ESTADO_MS > 0:
            self._timer_estado.start(self.INTERVALO_ESTADO_MS)

    # ------------------------------------------------------------------ montagem
    def _montar(self) -> None:
        central = QWidget()
        raiz = QHBoxLayout(central)

        # -- coluna da esquerda: scanner e opcoes
        esquerda = QVBoxLayout()
        self.grupo = QGroupBox()
        form = QFormLayout(self.grupo)
        self.combo_scanner = QComboBox()
        self.combo_scanner.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_scanner.setMinimumContentsLength(18)
        self.botao_atualizar = QPushButton()
        self.botao_endereco = QPushButton()
        self.combo_origem = _combo(CHAVE_ORIGEM)
        self.rotulo_alimentador = QLabel()
        self.rotulo_alimentador.setVisible(False)
        self.combo_cor = _combo(CHAVE_COR)
        self.combo_dpi = QComboBox()
        for dpi in configuracao.DPIS:
            self.combo_dpi.addItem(f"{dpi} dpi", dpi)
        self.combo_papel = _combo(CHAVE_PAPEL)
        self.botao_previa = QPushButton()
        self.rot_origem, self.rot_cor = QLabel(), QLabel()
        self.rot_resolucao, self.rot_papel = QLabel(), QLabel()
        form.addRow(self.combo_scanner)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(self.botao_atualizar)
        linha_botoes.addWidget(self.botao_endereco)
        form.addRow(linha_botoes)
        form.addRow(self.rot_origem, self.combo_origem)
        form.addRow(self.rotulo_alimentador)
        form.addRow(self.rot_cor, self.combo_cor)
        form.addRow(self.rot_resolucao, self.combo_dpi)
        form.addRow(self.rot_papel, self.combo_papel)
        form.addRow(self.botao_previa)
        esquerda.addWidget(self.grupo)

        self.botao_digitalizar = QPushButton()
        self.botao_digitalizar.setMinimumHeight(44)
        fonte = self.botao_digitalizar.font()
        fonte.setBold(True)
        fonte.setPointSize(fonte.pointSize() + 2)
        self.botao_digitalizar.setFont(fonte)
        self.botao_digitalizar.setDefault(True)
        self.botao_cancelar = QPushButton()
        self.botao_cancelar.setVisible(False)
        esquerda.addWidget(self.botao_digitalizar)
        esquerda.addWidget(self.botao_cancelar)
        self.rotulo_aviso = QLabel("")
        self.rotulo_aviso.setWordWrap(True)
        esquerda.addWidget(self.rotulo_aviso)
        esquerda.addStretch(1)
        lateral = QWidget()
        lateral.setLayout(esquerda)
        lateral.setFixedWidth(310)
        raiz.addWidget(lateral)

        # -- area das paginas
        direita = QVBoxLayout()
        barra = QHBoxLayout()
        self.botao_esquerda = QPushButton()
        self.botao_direita = QPushButton()
        self.botao_girar_e = QPushButton()
        self.botao_girar_d = QPushButton()
        self.botao_excluir = QPushButton()
        self.botao_limpar = QPushButton()
        for botao in (self.botao_esquerda, self.botao_direita, self.botao_girar_e,
                      self.botao_girar_d, self.botao_excluir):
            barra.addWidget(botao)
        barra.addStretch(1)
        barra.addWidget(self.botao_limpar)
        direita.addLayout(barra)

        self.lista = QListWidget()
        self.lista.setViewMode(QListView.ViewMode.IconMode)
        self.lista.setIconSize(QSize(150, 200))
        self.lista.setGridSize(QSize(176, 244))
        self.lista.setResizeMode(QListView.ResizeMode.Adjust)
        self.lista.setMovement(QListView.Movement.Snap)
        self.lista.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lista.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.setWordWrap(True)
        direita.addWidget(self.lista, 1)

        saida = QHBoxLayout()
        self.combo_formato = _combo(CHAVE_FORMATO)
        self.caixa_ocr = QCheckBox()
        self.botao_salvar = QPushButton()
        self.botao_salvar.setMinimumHeight(34)
        self.rot_salvar_como = QLabel()
        saida.addWidget(self.rot_salvar_como)
        saida.addWidget(self.combo_formato)
        saida.addWidget(self.caixa_ocr)
        saida.addStretch(1)
        saida.addWidget(self.botao_salvar)
        direita.addLayout(saida)
        raiz.addLayout(direita, 1)

        self.setCentralWidget(central)

        # -- menus
        self.menu_arquivo = self.menuBar().addMenu("")
        self.acao_digitalizar = QAction(self)
        self.acao_digitalizar.setShortcut(QKeySequence("Ctrl+D"))
        self.acao_salvar = QAction(self)
        self.acao_salvar.setShortcut(QKeySequence.StandardKey.Save)
        self.acao_sair = QAction(self)
        self.acao_sair.triggered.connect(self.close)
        self.menu_arquivo.addActions([self.acao_digitalizar, self.acao_salvar])
        self.menu_arquivo.addSeparator()
        self.menu_arquivo.addAction(self.acao_sair)

        self.menu_exibir = self.menuBar().addMenu("")
        self.menu_tema = self.menu_exibir.addMenu("")
        self.grupo_tema = QActionGroup(self)
        self.acoes_tema: dict[str, QAction] = {}
        for modo in tema.MODOS:
            acao = QAction(self, checkable=True)
            acao.triggered.connect(lambda _=False, m=modo: self.definir_tema(m))
            self.grupo_tema.addAction(acao)
            self.menu_tema.addAction(acao)
            self.acoes_tema[modo] = acao
        self.menu_idioma = self.menu_exibir.addMenu("")
        self.grupo_idioma = QActionGroup(self)
        self.acoes_idioma: dict[str, QAction] = {}
        for codigo in configuracao.IDIOMAS:
            acao = QAction(self, checkable=True)
            acao.triggered.connect(lambda _=False, c=codigo: self.definir_idioma(c))
            self.grupo_idioma.addAction(acao)
            self.menu_idioma.addAction(acao)
            self.acoes_idioma[codigo] = acao

        self.menu_ajuda = self.menuBar().addMenu("")
        self.acao_diagnostico = QAction(self)
        self.acao_diagnostico.triggered.connect(self.diagnosticar)
        self.acao_sobre = QAction(self)
        self.acao_sobre.triggered.connect(self._sobre)
        self.menu_ajuda.addActions([self.acao_diagnostico, self.acao_sobre])

        self.acao_excluir = QAction(self)
        self.acao_excluir.setShortcut(QKeySequence.StandardKey.Delete)
        self.lista.addAction(self.acao_excluir)

        # -- sinais
        self.botao_atualizar.clicked.connect(self.atualizar_scanners)
        self.botao_endereco.clicked.connect(self.adicionar_endereco)
        self.botao_previa.clicked.connect(self.abrir_previa)
        self.combo_scanner.activated.connect(self._scanner_escolhido)
        self.combo_origem.currentIndexChanged.connect(self._origem_mudou)
        self.combo_papel.activated.connect(self._papel_escolhido)
        self.botao_digitalizar.clicked.connect(self.digitalizar)
        self.acao_digitalizar.triggered.connect(self.digitalizar)
        self.botao_cancelar.clicked.connect(self._cancelar)
        self.botao_salvar.clicked.connect(self.salvar)
        self.acao_salvar.triggered.connect(self.salvar)
        self.botao_excluir.clicked.connect(self.excluir_selecionadas)
        self.acao_excluir.triggered.connect(self.excluir_selecionadas)
        self.botao_limpar.clicked.connect(self.limpar_tudo)
        self.botao_girar_d.clicked.connect(lambda: self.girar_selecionadas(90))
        self.botao_girar_e.clicked.connect(lambda: self.girar_selecionadas(-90))
        self.botao_esquerda.clicked.connect(lambda: self.mover_selecionada(-1))
        self.botao_direita.clicked.connect(lambda: self.mover_selecionada(1))
        self.lista.itemSelectionChanged.connect(self._atualizar_estado)
        self.lista.itemDoubleClicked.connect(self._abrir_pagina)
        self.lista.model().rowsMoved.connect(lambda *_: QTimer.singleShot(0, self._sincronizar_ordem))
        self.combo_formato.currentIndexChanged.connect(self._atualizar_estado)

        self.retraduzir()
        self.statusBar().showMessage(t("status.pronto"))

    def retraduzir(self) -> None:
        """Reaplica todos os textos de tela no idioma atual (a troca de idioma nao reinicia)."""
        self.grupo.setTitle(t("tela.scanner"))
        self.botao_atualizar.setText(t("tela.atualizar"))
        self.botao_endereco.setText(t("tela.adicionar_endereco"))
        self.botao_endereco.setToolTip(t("tela.adicionar_endereco.dica"))
        self.rot_origem.setText(t("tela.origem"))
        self.rot_cor.setText(t("tela.cor"))
        self.rot_resolucao.setText(t("tela.resolucao"))
        self.rot_papel.setText(t("tela.papel"))
        self.botao_previa.setText(t("tela.previa"))
        self.botao_previa.setToolTip(t("tela.previa.dica"))
        self.botao_digitalizar.setText(t("tela.digitalizar"))
        self.botao_cancelar.setText(t("tela.cancelar"))
        self.botao_esquerda.setText(t("tela.mover_esq"))
        self.botao_direita.setText(t("tela.mover_dir"))
        self.botao_girar_e.setText(t("tela.girar_e"))
        self.botao_girar_d.setText(t("tela.girar_d"))
        self.botao_excluir.setText(t("tela.excluir"))
        self.botao_limpar.setText(t("tela.limpar"))
        self.lista.setToolTip(t("tela.lista.dica"))
        self.rot_salvar_como.setText(t("tela.salvar_como"))
        self.caixa_ocr.setText(t("tela.ocr"))
        self.botao_salvar.setText(t("tela.salvar"))
        _retraduzir_combo(self.combo_origem, CHAVE_ORIGEM)
        _retraduzir_combo(self.combo_cor, CHAVE_COR)
        _retraduzir_combo(self.combo_formato, CHAVE_FORMATO)
        for i in range(self.combo_papel.count()):
            self.combo_papel.setItemText(i, self._rotulo_papel(self.combo_papel.itemData(i)))
        self._mostrar_papel_no_alimentador()
        self._renumerar()

        self.menu_arquivo.setTitle(t("menu.arquivo"))
        self.acao_digitalizar.setText(t("menu.digitalizar"))
        self.acao_salvar.setText(t("menu.salvar"))
        self.acao_sair.setText(t("menu.sair"))
        self.menu_exibir.setTitle(t("menu.exibir"))
        self.menu_tema.setTitle(t("menu.tema"))
        for modo, acao in self.acoes_tema.items():
            acao.setText(t(CHAVE_TEMA[modo]))
            acao.setChecked(modo == self._config.tema)
        self.menu_idioma.setTitle(t("menu.idioma"))
        for codigo, acao in self.acoes_idioma.items():
            acao.setText(t("menu.idioma.auto") if codigo == "auto" else i18n.NOMES[codigo])
            acao.setChecked(codigo == self._config.idioma)
        self.menu_ajuda.setTitle(t("menu.ajuda"))
        self.acao_diagnostico.setText(t("menu.diagnostico"))
        self.acao_sobre.setText(t("menu.sobre"))
        self._atualizar_estado()

    def _aplicar_config(self) -> None:
        c = self._config
        _escolher(self.combo_origem, c.origem)
        _escolher(self.combo_cor, c.cor)
        _escolher(self.combo_dpi, c.dpi)
        _escolher(self.combo_papel, c.papel)
        _escolher(self.combo_formato, c.formato)
        # Sem Tesseract a caixa aparece desmarcada e desabilitada; a preferencia fica guardada.
        self.caixa_ocr.setChecked(c.ocr and self._tesseract is not None)

    def _guardar_config(self) -> None:
        c = self._config
        c.scanner_id = self.combo_scanner.currentData() or c.scanner_id
        c.origem = self.combo_origem.currentData() or c.origem
        c.cor = self.combo_cor.currentData()
        c.dpi = self.combo_dpi.currentData() or c.dpi
        papel = self.combo_papel.currentData()
        c.papel = self._papel_antes_da_area if papel == "area" else papel
        c.formato = self.combo_formato.currentData()
        if self._tesseract is not None:
            c.ocr = self.caixa_ocr.isChecked()
        configuracao.salvar(c)

    # ------------------------------------------------------------------ tema e idioma
    def definir_tema(self, modo: str) -> None:
        self._config.tema = tema.aplicar(QApplication.instance(), modo)
        configuracao.salvar(self._config)
        for m, acao in self.acoes_tema.items():
            acao.setChecked(m == self._config.tema)

    def definir_idioma(self, codigo: str) -> None:
        """`codigo`: auto, pt, en, es ou zh. Troca textos da janela e dos dialogos padrao do Qt."""
        efetivo = i18n.definir_idioma(codigo)
        idioma.instalar(QApplication.instance(), efetivo)
        self._config.idioma = codigo if codigo in configuracao.IDIOMAS else "auto"
        configuracao.salvar(self._config)
        # O OCR acompanha o idioma: pt -> por+eng, es -> spa+eng, zh -> chi_sim+eng, en -> eng.
        self._tesseract = ocr.localizar(efetivo)
        self.retraduzir()
        self.statusBar().showMessage(t("status.pronto"))

    # ------------------------------------------------------------------ estado
    def _atualizar_estado(self) -> None:
        livre = not self._ocupado
        tem_paginas = len(self._documento) > 0
        selecionadas = len(self.lista.selectedItems())
        pdf = self.combo_formato.currentData() == "pdf"

        for w in (self.combo_scanner, self.botao_atualizar, self.botao_endereco,
                  self.combo_origem, self.combo_cor,
                  self.combo_dpi, self.combo_papel):
            w.setEnabled(livre)
        self.botao_digitalizar.setEnabled(livre and self._tem_scanner)
        self.acao_digitalizar.setEnabled(livre and self._tem_scanner)
        self.botao_previa.setEnabled(
            livre and self._tem_scanner and self._vidro_mm is not None
            and self.combo_origem.currentData() == "vidro"
            and hasattr(self._scanner, "previa"))
        self.botao_salvar.setEnabled(livre and tem_paginas)
        self.acao_salvar.setEnabled(livre and tem_paginas)
        self.combo_formato.setEnabled(livre)
        self.botao_limpar.setEnabled(livre and tem_paginas)
        for botao in (self.botao_girar_d, self.botao_girar_e, self.botao_excluir):
            botao.setEnabled(livre and selecionadas > 0)
        self.botao_esquerda.setEnabled(livre and selecionadas == 1 and self.lista.currentRow() > 0)
        self.botao_direita.setEnabled(
            livre and selecionadas == 1 and 0 <= self.lista.currentRow() < self.lista.count() - 1)

        # OCR so' vale para PDF e so' se o Tesseract existe.
        self.caixa_ocr.setEnabled(livre and pdf and self._tesseract is not None)
        self.caixa_ocr.setToolTip(t("tela.ocr.sem_tesseract") if self._tesseract is None else "")
        self.botao_cancelar.setVisible(self._digitalizando is not None)

    def _ocupar(self, ocupado: bool, mensagem: str = "") -> None:
        self._ocupado = ocupado
        if mensagem:
            self.statusBar().showMessage(mensagem)
        self._atualizar_estado()

    def _guardar_trabalho(self, trabalho) -> None:
        self._trabalhos.add(trabalho)
        trabalho.finished.connect(lambda t_=trabalho: self._trabalhos.discard(t_))

    # ------------------------------------------------------------------ mensagens (sobrescrevivel nos testes)
    def _avisar(self, titulo: str, texto: str) -> None:
        QMessageBox.warning(self, titulo, texto)

    def _informar(self, titulo: str, texto: str) -> None:
        QMessageBox.information(self, titulo, texto)

    def _confirmar(self, titulo: str, texto: str) -> bool:
        resposta = QMessageBox.question(self, titulo, texto,
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
        return resposta == QMessageBox.StandardButton.Yes

    def _pedir_endereco(self) -> str | None:
        texto, ok = QInputDialog.getText(self, t("dlg.endereco.titulo"), t("dlg.endereco.texto"))
        return texto.strip() if ok and texto.strip() else None

    def _pedir_destino(self, sugestao: pathlib.Path, formato: str) -> pathlib.Path | None:
        caminho, _ = QFileDialog.getSaveFileName(self, t("dlg.salvar.titulo"), str(sugestao),
                                                 t(CHAVE_FILTRO[formato]))
        return pathlib.Path(caminho) if caminho else None

    def _depois_de_salvar(self, arquivos: list[pathlib.Path], aviso: str) -> None:
        caixa = QMessageBox(self)
        caixa.setWindowTitle(t("dlg.salvo.titulo"))
        texto = "\n".join(str(a) for a in arquivos[:6])
        if len(arquivos) > 6:
            texto += "\n" + t("dlg.salvo.mais", n=len(arquivos) - 6)
        caixa.setText(t("dlg.salvo.texto", lista=texto) + (f"\n\n{aviso}" if aviso else ""))
        abrir = caixa.addButton(t("dlg.abrir"), QMessageBox.ButtonRole.AcceptRole)
        pasta = caixa.addButton(t("dlg.abrir_pasta"), QMessageBox.ButtonRole.ActionRole)
        caixa.addButton(t("dlg.fechar"), QMessageBox.ButtonRole.RejectRole)
        caixa.exec()
        if caixa.clickedButton() is abrir:
            os.startfile(str(arquivos[0]))
        elif caixa.clickedButton() is pasta:
            os.startfile(str(arquivos[0].parent))

    # ------------------------------------------------------------------ scanners
    def atualizar_scanners(self) -> None:
        if self._ocupado:
            return
        self._ocupar(True, t("status.procurando"))
        trabalho = TrabalhoListar(self._scanner, self._config.scanner_id)
        trabalho.pronto.connect(self._scanners_listados)
        trabalho.erro.connect(self._falha_ao_listar)
        self._guardar_trabalho(trabalho)
        trabalho.start()

    def adicionar_endereco(self) -> None:
        if self._ocupado:
            return
        endereco = self._pedir_endereco()
        if not endereco:
            return
        if any(c.isspace() for c in endereco) or len(endereco) > 200:
            self._avisar(t("dlg.endereco_invalido.titulo"), t("dlg.endereco_invalido.texto"))
            return
        if endereco not in self._config.enderecos_escl:
            self._config.enderecos_escl.insert(0, endereco)
            configuracao.salvar(self._config)
        self.atualizar_scanners()

    def _scanners_listados(self, dispositivos, capacidades) -> None:
        self.combo_scanner.clear()
        for d in dispositivos:
            self.combo_scanner.addItem(d.nome, d.id)
        self._tem_scanner = bool(dispositivos)
        self._reiniciar_estado_do_alimentador()
        if dispositivos:
            _escolher(self.combo_scanner, escolher_preferido(dispositivos, self._config.scanner_id).id)
            self._aplicar_capacidades(capacidades)
            self.rotulo_aviso.setText("")
            self._ocupar(False, t("status.encontrados", n=len(dispositivos)))
            self._sondar_estado()
        else:
            self.rotulo_aviso.setText(t("aviso.nenhum_scanner"))
            self._ocupar(False, t("status.nenhum"))

    def _falha_ao_listar(self, mensagem: str) -> None:
        self._tem_scanner = False
        self.rotulo_aviso.setText(mensagem)
        self._ocupar(False, mensagem)

    def _scanner_escolhido(self) -> None:
        dispositivo = self.combo_scanner.currentData()
        if not dispositivo or self._ocupado:
            return
        self._reiniciar_estado_do_alimentador()
        self._ocupar(True, t("status.consultando"))
        trabalho = TrabalhoCapacidades(self._scanner, dispositivo)
        trabalho.pronto.connect(lambda c: (self._aplicar_capacidades(c), self._ocupar(False, t("status.pronto")),
                                           self._sondar_estado()))
        trabalho.erro.connect(lambda m: (self.rotulo_aviso.setText(m), self._ocupar(False, m)))
        self._guardar_trabalho(trabalho)
        trabalho.start()

    def _aplicar_capacidades(self, capacidades: Capacidades | None) -> None:
        if capacidades is None:
            return
        anterior_origem = self.combo_origem.currentData()
        anterior_dpi = self.combo_dpi.currentData()
        self.combo_origem.blockSignals(True)
        self.combo_origem.clear()
        for origem in capacidades.origens:
            self.combo_origem.addItem(t(CHAVE_ORIGEM[origem]), origem)
        _escolher(self.combo_origem, anterior_origem)
        self.combo_origem.blockSignals(False)
        self.combo_dpi.clear()
        for dpi in capacidades.dpis:
            self.combo_dpi.addItem(f"{dpi} dpi", dpi)
        _escolher(self.combo_dpi, anterior_dpi)
        self._vidro_mm = capacidades.vidro_mm
        if self._regiao_mm is not None:                 # a area era de outro scanner/vidro
            self._definir_regiao(None)
        self._atualizar_estado()

    # ------------------------------------------------------------------ papel no alimentador
    def _reiniciar_estado_do_alimentador(self) -> None:
        self._papel_no_alimentador = None
        self._papel_ja_lido = False
        self._falhas_estado = 0
        self._mostrar_papel_no_alimentador()
        if self.INTERVALO_ESTADO_MS > 0 and hasattr(self, "_timer_estado"):
            self._timer_estado.start(self.INTERVALO_ESTADO_MS)

    def _mostrar_papel_no_alimentador(self) -> None:
        papel = self._papel_no_alimentador
        self.rotulo_alimentador.setVisible(papel is not None)
        if papel is not None:
            self.rotulo_alimentador.setText(
                t("tela.alimentador.com_papel" if papel else "tela.alimentador.vazio"))

    def _sondar_estado(self) -> None:
        """Pergunta ao scanner se ha' papel no alimentador (so' quando nada mais esta' acontecendo)."""
        dispositivo = self.combo_scanner.currentData()
        if (self._ocupado or self._sondando or not self._tem_scanner or not dispositivo
                or not hasattr(self._scanner, "estado") or not self.isVisible()):
            return
        self._sondando = True
        trabalho = TrabalhoEstado(self._scanner, dispositivo)
        trabalho.pronto.connect(self._estado_recebido)
        trabalho.erro.connect(self._estado_falhou)
        trabalho.finished.connect(lambda: setattr(self, "_sondando", False))
        self._guardar_trabalho(trabalho)
        trabalho.start()

    def _estado_falhou(self, _mensagem: str) -> None:
        self._falhas_estado += 1
        if self._falhas_estado >= 3:                    # scanner fora do ar: para de insistir
            self._timer_estado.stop()

    def _estado_recebido(self, estado) -> None:
        self._falhas_estado = 0
        self._aplicar_papel(estado.papel)

    def _aplicar_papel(self, papel: bool | None) -> None:
        """Mostra o indicador e troca a origem so' quando o estado MUDA (a escolha manual vale
        ate' a proxima mudanca). Na primeira leitura so' o 'com papel' escolhe o alimentador."""
        anterior, ja_lido = self._papel_no_alimentador, self._papel_ja_lido
        self._papel_no_alimentador = papel
        self._mostrar_papel_no_alimentador()
        if papel is None:
            return
        self._papel_ja_lido = True
        if self._ocupado or self._digitalizando is not None:
            return
        mudou = (not ja_lido) or anterior != papel
        if not mudou:
            return
        origem = self.combo_origem.currentData()
        if papel and origem == "vidro" and self.combo_origem.findData("alimentador") >= 0:
            _escolher(self.combo_origem, "alimentador")
        elif not papel and ja_lido and origem == "alimentador" and self.combo_origem.findData("vidro") >= 0:
            _escolher(self.combo_origem, "vidro")
        self._origem_mudou()

    # ------------------------------------------------------------------ previa e area
    def _rotulo_papel(self, valor) -> str:
        if valor == "area" and self._regiao_mm is not None:
            return t("papel.area", largura=f"{self._regiao_mm[2]:.0f}", altura=f"{self._regiao_mm[3]:.0f}")
        return t(CHAVE_PAPEL.get(valor, "papel.total"))

    def _definir_regiao(self, regiao: tuple[float, float, float, float] | None) -> None:
        """Poe ou tira a 'Area selecionada' do combo de papel."""
        indice = self.combo_papel.findData("area")
        if regiao is None:
            self._regiao_mm = None
            if indice >= 0:
                era_a_area = self.combo_papel.currentIndex() == indice
                self.combo_papel.removeItem(indice)
                if era_a_area:
                    _escolher(self.combo_papel, self._papel_antes_da_area)
            return
        if indice < 0:
            self._papel_antes_da_area = self.combo_papel.currentData() or self._papel_antes_da_area
            self.combo_papel.addItem("", "area")
            indice = self.combo_papel.findData("area")
        self._regiao_mm = regiao
        self.combo_papel.setItemText(indice, self._rotulo_papel("area"))
        self.combo_papel.setCurrentIndex(indice)

    def _papel_escolhido(self) -> None:
        """O usuario escolheu um papel no combo: sai a area selecionada."""
        if self._regiao_mm is not None and self.combo_papel.currentData() != "area":
            escolhido = self.combo_papel.currentData()
            self._definir_regiao(None)
            _escolher(self.combo_papel, escolhido)

    def _origem_mudou(self) -> None:
        if self.combo_origem.currentData() != "vidro" and self._regiao_mm is not None:
            self._definir_regiao(None)
        self._atualizar_estado()

    def abrir_previa(self) -> None:
        dispositivo = self.combo_scanner.currentData()
        if self._ocupado or not dispositivo or self._vidro_mm is None:
            return
        self._ocupar(True, t("status.previa"))
        trabalho = TrabalhoPrevia(self._scanner, dispositivo)
        trabalho.pronto.connect(self._previa_pronta)
        trabalho.erro.connect(self._falha_na_previa)
        self._guardar_trabalho(trabalho)
        trabalho.start()

    def _previa_pronta(self, imagem) -> None:
        self._ocupar(False, t("status.previa_pronta"))
        resultado = self._mostrar_previa(imagem)
        if resultado == "atualizar":
            QTimer.singleShot(0, self.abrir_previa)
        elif resultado is not None and resultado != "cancelar":
            self._definir_regiao(resultado)

    def _mostrar_previa(self, imagem):
        """Abre a janela da previa. Devolve a area (mm), "atualizar", "cancelar" ou None.
        Sobrescrevivel nos testes (a janela de verdade e' modal)."""
        dialogo = DialogoPrevia(imagem, self._vidro_mm, self._regiao_mm, self)
        dialogo.pedido_atualizar.connect(lambda: dialogo.done(2))
        codigo = dialogo.exec()
        if codigo == 2:
            return "atualizar"
        if codigo == DialogoPrevia.DialogCode.Accepted:
            return dialogo.regiao_mm
        return "cancelar"

    def _falha_na_previa(self, mensagem: str) -> None:
        self._ocupar(False, t("status.previa_falha"))
        self._avisar(t("dlg.previa_falha.titulo"), mensagem)

    # ------------------------------------------------------------------ digitalizar
    def _opcoes(self) -> Opcoes:
        papel = self.combo_papel.currentData()
        regiao = None
        if papel == "area":
            papel, regiao = "total", self._regiao_mm
        return Opcoes(origem=self.combo_origem.currentData() or "vidro",
                      cor=self.combo_cor.currentData(),
                      dpi=self.combo_dpi.currentData() or 300,
                      papel=papel, regiao_mm=regiao)

    def digitalizar(self) -> None:
        if self._ocupado or not self._tem_scanner:
            return
        dispositivo = self.combo_scanner.currentData()
        if not dispositivo:
            return
        self._guardar_config()
        opcoes = self._opcoes()
        trabalho = TrabalhoDigitalizar(self._scanner, dispositivo, opcoes)
        self._digitalizando = trabalho
        self._novas = 0
        trabalho.pagina.connect(lambda imagem, o=opcoes: self._pagina_recebida(imagem, o.dpi))
        trabalho.erro.connect(self._falha_ao_digitalizar)
        trabalho.concluido.connect(self._digitalizacao_concluida)
        self._guardar_trabalho(trabalho)
        self.rotulo_aviso.setText("")
        self._ocupar(True, t("status.digitalizando"))
        trabalho.start()

    def _cancelar(self) -> None:
        if self._digitalizando is not None:
            self._digitalizando.cancelar()
            self.statusBar().showMessage(t("status.cancelando"))

    def _pagina_recebida(self, imagem, dpi: int) -> None:
        dpi = int(imagem.info.get("dscan_dpi", dpi))     # o eSCL pode ter baixado a resolucao
        pagina = self._documento.adicionar(imagem, dpi)
        self._novas += 1
        self._salvo = False
        self._acrescentar_item(pagina)
        self.statusBar().showMessage(t("status.recebendo", n=self._novas))

    def _falha_ao_digitalizar(self, mensagem: str) -> None:
        self.rotulo_aviso.setText(mensagem)
        if _CODIGO_HEX.search(mensagem):                 # erro sem mensagem propria: sugere o diagnostico
            mensagem += "\n\n" + t("dlg.digitalizar_falha.dica")
        self._avisar(t("dlg.digitalizar_falha.titulo"), mensagem)

    def _digitalizacao_concluida(self, total: int) -> None:
        self._digitalizando = None
        texto = t("status.concluido", n=total) if total else t("status.nenhuma_pagina")
        self._ocupar(False, texto)
        if total:
            self.lista.scrollToBottom()

    # ------------------------------------------------------------------ lista de paginas
    def _acrescentar_item(self, pagina) -> None:
        item = QListWidgetItem()
        pixmap = QPixmap()
        pixmap.loadFromData(pagina.miniatura)
        item.setIcon(QIcon(pixmap))
        item.setData(Qt.ItemDataRole.UserRole, pagina.id)
        self.lista.addItem(item)
        self._renumerar()

    def _renumerar(self) -> None:
        for linha in range(self.lista.count()):
            self.lista.item(linha).setText(t("tela.pagina", n=linha + 1))

    def _ids_selecionados(self) -> list[int]:
        return [self.lista.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.lista.count()) if self.lista.item(i).isSelected()]

    def _sincronizar_ordem(self) -> None:
        """A lista e' a verdade sobre a ordem (o arraste a muda); o Documento acompanha."""
        ids = [self.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lista.count())]
        if sorted(ids) == sorted(p.id for p in self._documento.paginas):
            if ids != [p.id for p in self._documento.paginas]:
                self._documento.reordenar(ids)
                self._salvo = False
        self._renumerar()
        self._atualizar_estado()

    def _item_do_id(self, id_: int) -> QListWidgetItem | None:
        for i in range(self.lista.count()):
            if self.lista.item(i).data(Qt.ItemDataRole.UserRole) == id_:
                return self.lista.item(i)
        return None

    def excluir_selecionadas(self) -> None:
        if self._ocupado:
            return
        for id_ in self._ids_selecionados():
            self._documento.remover(id_)
            item = self._item_do_id(id_)
            if item is not None:
                self.lista.takeItem(self.lista.row(item))
        self._salvo = False
        self._renumerar()
        self._atualizar_estado()

    def girar_selecionadas(self, graus: int) -> None:
        if self._ocupado:
            return
        for id_ in self._ids_selecionados():
            self._documento.girar(id_, graus)
            pagina = next(p for p in self._documento.paginas if p.id == id_)
            pixmap = QPixmap()
            pixmap.loadFromData(pagina.miniatura)
            item = self._item_do_id(id_)
            if item is not None:
                item.setIcon(QIcon(pixmap))
        self._salvo = False

    def mover_selecionada(self, passo: int) -> None:
        if self._ocupado:
            return
        linha = self.lista.currentRow()
        destino = linha + passo
        if linha < 0 or not 0 <= destino < self.lista.count():
            return
        item = self.lista.takeItem(linha)
        self.lista.insertItem(destino, item)
        self.lista.setCurrentRow(destino)
        self._sincronizar_ordem()

    def limpar_tudo(self) -> None:
        if self._ocupado or not len(self._documento):
            return
        if not self._salvo and not self._confirmar(t("dlg.limpar.titulo"), t("dlg.limpar.texto")):
            return
        self._documento.limpar()
        self.lista.clear()
        self._salvo = True
        self._atualizar_estado()

    def _abrir_pagina(self, item: QListWidgetItem) -> None:
        id_ = item.data(Qt.ItemDataRole.UserRole)
        for pagina in self._documento.paginas:
            if pagina.id == id_:
                os.startfile(str(pagina.caminho))
                return

    # ------------------------------------------------------------------ salvar
    def _sugestao_de_nome(self) -> pathlib.Path:
        pasta = pathlib.Path(self._config.pasta_saida) if self._config.pasta_saida else (
            pathlib.Path.home() / "Documents")
        if not pasta.is_dir():
            pasta = pathlib.Path.home()
        nome = t("arquivo.nome", data=datetime.datetime.now().strftime("%Y-%m-%d %H.%M"))
        return pasta / f"{nome}.{self.combo_formato.currentData()}"

    def salvar(self) -> None:
        if self._ocupado or not len(self._documento):
            return
        self._sincronizar_ordem()
        formato = self.combo_formato.currentData()
        destino = self._pedir_destino(self._sugestao_de_nome(), formato)
        if destino is None:
            return
        if formato != "pdf":
            existentes = [c for c in exportar.caminhos_previstos(destino, len(self._documento), formato)
                          if c.exists()]
            if existentes and not self._confirmar(
                    t("dlg.substituir.titulo"), t("dlg.substituir.texto", n=len(existentes))):
                return
        self._guardar_config()
        self._config.pasta_saida = str(destino.parent)
        configuracao.salvar(self._config)

        paginas = self._documento.caminhos()
        dpi = self.combo_dpi.currentData() or 300
        usar_ocr = self.caixa_ocr.isChecked() and formato == "pdf"
        tesseract = self._tesseract
        trabalho = TrabalhoSalvar(
            lambda: exportar.exportar(paginas, destino, formato, dpi, usar_ocr, tesseract))
        trabalho.pronto.connect(self._salvo_com_sucesso)
        trabalho.erro.connect(self._falha_ao_salvar)
        self._guardar_trabalho(trabalho)
        self._ocupar(True, t("status.salvando_ocr") if usar_ocr and tesseract else t("status.salvando"))
        trabalho.start()

    def _salvo_com_sucesso(self, resultado) -> None:
        arquivos, aviso = resultado
        self._salvo = True
        self._ultimo_salvo = list(arquivos)
        self._ocupar(False, t("status.salvo", caminho=arquivos[0]))
        self._depois_de_salvar(list(arquivos), aviso)

    def _falha_ao_salvar(self, mensagem: str) -> None:
        self._ocupar(False, t("status.falha_salvar"))
        self._avisar(t("dlg.salvar_falha.titulo"), mensagem)

    # ------------------------------------------------------------------ diagnostico
    def diagnosticar(self) -> None:
        """Grava em diagnostico.txt tudo o que o driver do scanner expoe (para suporte)."""
        dispositivo = self.combo_scanner.currentData()
        gerar = getattr(self._scanner, "diagnostico", None)
        if self._ocupado or not dispositivo or gerar is None:
            self._informar(t("dlg.diagnostico.titulo"), t("dlg.diagnostico.escolha"))
            return
        destino = log_interno.pasta_de_dados() / "diagnostico.txt"

        def trabalho():
            self._scanner.preparar_thread()
            try:
                texto = gerar(dispositivo)
            finally:
                self._scanner.encerrar_thread()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
            return destino

        tarefa = TrabalhoSalvar(trabalho)
        tarefa.pronto.connect(self._diagnostico_pronto)
        tarefa.erro.connect(lambda m: (self._ocupar(False, t("status.diagnostico_falha")),
                                       self._avisar(t("dlg.diagnostico.titulo"), m)))
        self._guardar_trabalho(tarefa)
        self._ocupar(True, t("status.diagnostico_lendo"))
        tarefa.start()

    def _diagnostico_pronto(self, caminho) -> None:
        self._ocupar(False, t("status.diagnostico_salvo", caminho=caminho))
        self._informar(t("dlg.diagnostico.pronto.titulo"), t("dlg.diagnostico.pronto.texto", caminho=caminho))

    # ------------------------------------------------------------------ diversos
    def _sobre(self) -> None:
        ocr_texto = t("dlg.sobre.ocr_sim") if self._tesseract else t("dlg.sobre.ocr_nao")
        self._informar(t("dlg.sobre.titulo", nome=NOME),
                       t("dlg.sobre.texto", nome=NOME, versao=VERSAO, ocr=ocr_texto))

    def aguardar_trabalhos(self, limite_ms: int = 30000) -> None:
        """Espera as threads terminarem (usado ao fechar e nos testes)."""
        for trabalho in list(self._trabalhos):
            trabalho.wait(limite_ms)

    def closeEvent(self, evento: QCloseEvent) -> None:
        if self._ocupado and self._digitalizando is None:
            if not self._confirmar(t("dlg.sair.titulo"), t("dlg.sair.ocupado")):
                evento.ignore()
                return
        if not self._salvo and len(self._documento) and not self._confirmar(
                t("dlg.sair.titulo"), t("dlg.sair.nao_salvas")):
            evento.ignore()
            return
        self._timer_estado.stop()
        if self._digitalizando is not None:
            self._digitalizando.cancelar()
        self.aguardar_trabalhos()
        self._guardar_config()
        self._documento.descartar()
        evento.accept()
