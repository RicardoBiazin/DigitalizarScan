"""Threads de trabalho: nada de COM ou OCR na thread da interface."""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from digitalizarscan import log_interno
from digitalizarscan.i18n import t
from digitalizarscan.scanner.base import ErroScanner, Opcoes, Scanner, escolher_preferido

log = log_interno.obter(__name__)


class TrabalhoListar(QThread):
    """Lista os scanners e as capacidades do escolhido."""

    pronto = Signal(object, object)      # list[Dispositivo], Capacidades | None
    erro = Signal(str)

    def __init__(self, scanner: Scanner, preferido: str = "", parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._preferido = preferido

    def run(self) -> None:
        self._scanner.preparar_thread()
        try:
            dispositivos = self._scanner.listar()
            capacidades = None
            if dispositivos:
                escolhido = escolher_preferido(dispositivos, self._preferido)
                try:
                    capacidades = self._scanner.capacidades(escolhido.id)
                except ErroScanner as exc:
                    log.info("capacidades indisponiveis: %s", exc)
            self.pronto.emit(dispositivos, capacidades)
        except ErroScanner as exc:
            self.erro.emit(str(exc))
        except Exception as exc:            # noqa: BLE001
            log.exception("falha ao listar scanners")
            self.erro.emit(t("falha.listar", erro=exc))
        finally:
            self._scanner.encerrar_thread()


class TrabalhoCapacidades(QThread):
    pronto = Signal(object)
    erro = Signal(str)

    def __init__(self, scanner: Scanner, dispositivo_id: str, parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._id = dispositivo_id

    def run(self) -> None:
        self._scanner.preparar_thread()
        try:
            self.pronto.emit(self._scanner.capacidades(self._id))
        except ErroScanner as exc:
            self.erro.emit(str(exc))
        except Exception as exc:            # noqa: BLE001
            log.exception("falha ao ler capacidades")
            self.erro.emit(t("falha.capacidades", erro=exc))
        finally:
            self._scanner.encerrar_thread()


class TrabalhoDigitalizar(QThread):
    pagina = Signal(object)              # PIL.Image
    erro = Signal(str)
    concluido = Signal(int)              # quantas paginas entraram

    def __init__(self, scanner: Scanner, dispositivo_id: str, opcoes: Opcoes, parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._id = dispositivo_id
        self._opcoes = opcoes
        self._parar = threading.Event()

    def cancelar(self) -> None:
        self._parar.set()

    def run(self) -> None:
        total = 0
        self._scanner.preparar_thread()
        try:
            for imagem in self._scanner.digitalizar(self._id, self._opcoes, self._parar.is_set):
                total += 1
                self.pagina.emit(imagem)
        except ErroScanner as exc:
            self.erro.emit(str(exc))
        except Exception as exc:            # noqa: BLE001
            log.exception("falha ao digitalizar")
            self.erro.emit(t("falha.digitalizar", erro=exc))
        finally:
            self._scanner.encerrar_thread()
            self.concluido.emit(total)


class TrabalhoSalvar(QThread):
    """Grava o PDF/imagens (e roda o OCR, que demora) fora da thread da interface."""

    pronto = Signal(object)              # lista de caminhos gravados
    erro = Signal(str)

    def __init__(self, funcao, parent=None):
        super().__init__(parent)
        self._funcao = funcao

    def run(self) -> None:
        try:
            self.pronto.emit(self._funcao())
        except Exception as exc:            # noqa: BLE001
            log.exception("falha ao salvar")
            self.erro.emit(str(exc) or t("falha.salvar"))


class TrabalhoEstado(QThread):
    """Pergunta ao scanner se ha' papel no alimentador (curto; roda a cada poucos segundos)."""

    pronto = Signal(object)              # EstadoScanner
    erro = Signal(str)

    def __init__(self, scanner: Scanner, dispositivo_id: str, parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._id = dispositivo_id

    def run(self) -> None:
        self._scanner.preparar_thread()
        try:
            self.pronto.emit(self._scanner.estado(self._id))
        except Exception as exc:            # noqa: BLE001 - o sinal so' informa; a janela decide
            self.erro.emit(str(exc))
        finally:
            self._scanner.encerrar_thread()


class TrabalhoPrevia(QThread):
    """Previa do vidro inteiro em baixa resolucao."""

    pronto = Signal(object)              # PIL.Image
    erro = Signal(str)

    def __init__(self, scanner: Scanner, dispositivo_id: str, parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._id = dispositivo_id

    def run(self) -> None:
        self._scanner.preparar_thread()
        try:
            self.pronto.emit(self._scanner.previa(self._id))
        except ErroScanner as exc:
            self.erro.emit(str(exc))
        except Exception as exc:            # noqa: BLE001
            log.exception("falha na previa")
            self.erro.emit(t("falha.previa", erro=exc))
        finally:
            self._scanner.encerrar_thread()
