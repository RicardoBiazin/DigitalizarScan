"""Janela de previa do vidro: mostra o vidro inteiro e deixa arrastar um retangulo.

A imagem da previa cobre o vidro todo, entao uma posicao na imagem vira milimetros do vidro por
uma regra de tres (`selecao_para_mm`, funcao pura). A regiao e' relativa ao canto superior
esquerdo da propria imagem: o mesmo sistema de coordenadas que o scanner usa ao digitalizar.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QRubberBand,
                               QVBoxLayout)

from digitalizarscan.i18n import t

#: Area minima util (mm): um clique solto nao vira uma selecao de 0 mm.
MINIMO_MM = 5.0
LIMITE_TELA = QSize(620, 720)


def selecao_para_mm(retangulo: tuple[float, float, float, float],
                    tamanho_imagem: tuple[float, float],
                    vidro_mm: tuple[float, float]) -> tuple[float, float, float, float] | None:
    """(x0, y0, x1, y1) na imagem exibida -> (x, y, largura, altura) em mm do vidro.

    Aceita os cantos em qualquer ordem, recorta ao que esta' dentro da imagem e devolve None se a
    area ficar menor que MINIMO_MM em algum lado.
    """
    largura_px, altura_px = tamanho_imagem
    if largura_px <= 0 or altura_px <= 0:
        return None
    x0, x1 = sorted((retangulo[0], retangulo[2]))
    y0, y1 = sorted((retangulo[1], retangulo[3]))
    x0, x1 = max(0.0, x0), min(float(largura_px), x1)
    y0, y1 = max(0.0, y0), min(float(altura_px), y1)
    if x1 <= x0 or y1 <= y0:
        return None
    fx, fy = vidro_mm[0] / largura_px, vidro_mm[1] / altura_px
    x, y, l, a = x0 * fx, y0 * fy, (x1 - x0) * fx, (y1 - y0) * fy
    if l < MINIMO_MM or a < MINIMO_MM:
        return None
    return (round(x, 1), round(y, 1), round(l, 1), round(a, 1))


def mm_para_selecao(regiao_mm: tuple[float, float, float, float],
                    tamanho_imagem: tuple[float, float],
                    vidro_mm: tuple[float, float]) -> tuple[float, float, float, float]:
    """Inverso de `selecao_para_mm`: para reabrir a previa com a area ja' escolhida."""
    fx, fy = tamanho_imagem[0] / vidro_mm[0], tamanho_imagem[1] / vidro_mm[1]
    x, y, l, a = regiao_mm
    return (x * fx, y * fy, (x + l) * fx, (y + a) * fy)


def para_pixmap(imagem: Image.Image, maximo: QSize = LIMITE_TELA) -> QPixmap:
    rgb = imagem.convert("RGB")
    dados = rgb.tobytes("raw", "RGB")
    qimagem = QImage(dados, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()
    pixmap = QPixmap.fromImage(qimagem)
    return pixmap.scaled(maximo, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class _Visor(QLabel):
    """A imagem com o retangulo de selecao por arraste do mouse."""

    mudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._faixa = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._origem = QPoint()
        self._selecao: QRect | None = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def selecao(self) -> QRect | None:
        return self._selecao

    def definir_selecao(self, retangulo: QRect | None) -> None:
        self._selecao = retangulo.normalized() if retangulo is not None else None
        if self._selecao is None:
            self._faixa.hide()
        else:
            self._faixa.setGeometry(self._selecao)
            self._faixa.show()
        self.mudou.emit()

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self._origem = evento.position().toPoint()
            self._faixa.setGeometry(QRect(self._origem, QSize()))
            self._faixa.show()

    def mouseMoveEvent(self, evento) -> None:
        if evento.buttons() & Qt.MouseButton.LeftButton:
            area = QRect(self._origem, evento.position().toPoint()).normalized()
            self._faixa.setGeometry(area.intersected(self.rect()))

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            area = QRect(self._origem, evento.position().toPoint()).normalized().intersected(self.rect())
            self.definir_selecao(area if area.width() > 2 and area.height() > 2 else None)


class DialogoPrevia(QDialog):
    pedido_atualizar = Signal()

    def __init__(self, imagem: Image.Image, vidro_mm: tuple[float, float],
                 regiao_mm: tuple[float, float, float, float] | None = None, parent=None):
        super().__init__(parent)
        self._vidro_mm = vidro_mm
        self.regiao_mm: tuple[float, float, float, float] | None = regiao_mm
        self.setWindowTitle(t("previa.titulo"))

        self.dica = QLabel(t("previa.dica"))
        self.dica.setWordWrap(True)
        self.visor = _Visor()
        self.rotulo_selecao = QLabel()
        self.botao_atualizar = QPushButton(t("previa.atualizar"))
        self.botao_limpar = QPushButton(t("previa.limpar"))
        self.botao_usar = QPushButton(t("previa.usar"))
        self.botao_usar.setDefault(True)
        self.botao_cancelar = QPushButton(t("previa.cancelar"))

        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_atualizar)
        botoes.addWidget(self.botao_limpar)
        botoes.addStretch(1)
        botoes.addWidget(self.botao_usar)
        botoes.addWidget(self.botao_cancelar)
        coluna = QVBoxLayout(self)
        coluna.addWidget(self.dica)
        coluna.addWidget(self.visor, 1, Qt.AlignmentFlag.AlignHCenter)
        coluna.addWidget(self.rotulo_selecao)
        coluna.addLayout(botoes)

        self.botao_atualizar.clicked.connect(self.pedido_atualizar)
        self.botao_limpar.clicked.connect(lambda: self.visor.definir_selecao(None))
        self.botao_usar.clicked.connect(self._usar)
        self.botao_cancelar.clicked.connect(self.reject)
        self.visor.mudou.connect(self._atualizar_rotulo)

        self.definir_imagem(imagem)
        if regiao_mm is not None:
            x0, y0, x1, y1 = mm_para_selecao(regiao_mm, self._tamanho_exibido(), vidro_mm)
            self.visor.definir_selecao(QRect(round(x0), round(y0), round(x1 - x0), round(y1 - y0)))

    def _tamanho_exibido(self) -> tuple[int, int]:
        return self.visor.width(), self.visor.height()

    def definir_imagem(self, imagem: Image.Image) -> None:
        pixmap = para_pixmap(imagem)
        self.visor.setPixmap(pixmap)
        self.visor.setFixedSize(pixmap.size())
        self.visor.definir_selecao(None)

    def selecao_mm(self) -> tuple[float, float, float, float] | None:
        retangulo = self.visor.selecao()
        if retangulo is None:
            return None
        return selecao_para_mm((retangulo.left(), retangulo.top(), retangulo.right() + 1, retangulo.bottom() + 1),
                               self._tamanho_exibido(), self._vidro_mm)

    def _atualizar_rotulo(self) -> None:
        regiao = self.selecao_mm()
        if regiao is None:
            self.rotulo_selecao.setText(t("previa.sem_selecao"))
        else:
            self.rotulo_selecao.setText(t("previa.selecao", largura=f"{regiao[2]:.0f}", altura=f"{regiao[3]:.0f}"))
        self.botao_usar.setEnabled(regiao is not None)

    def _usar(self) -> None:
        self.regiao_mm = self.selecao_mm()
        self.accept()
