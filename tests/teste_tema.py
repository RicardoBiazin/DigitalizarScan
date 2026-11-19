"""Tema de cor: sistema, claro e escuro."""

import os

from ajudantes import encerrar, igual, verificar

# O plugin "offscreen" ignora setColorScheme; o "windows" aplica (e nada aparece: nao ha' show()).
os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from digitalizarscan import configuracao, tema
from digitalizarscan.interface.janela_principal import JanelaPrincipal
from digitalizarscan.scanner.falso import ScannerFalso

app = QApplication([])
JanelaPrincipal.INTERVALO_ESTADO_MS = 0

# -- aplicar muda o esquema de cor da aplicacao
igual(tema.aplicar(app, "escuro"), "escuro", "devolve o modo")
igual(app.styleHints().colorScheme(), Qt.ColorScheme.Dark, "escuro")
verificar(app.palette().window().color().lightness() < 128, "paleta escura de verdade")
igual(tema.aplicar(app, "claro"), "claro", "claro")
igual(app.styleHints().colorScheme(), Qt.ColorScheme.Light, "claro")
verificar(app.palette().window().color().lightness() > 128, "paleta clara de verdade")
igual(tema.aplicar(app, "sistema"), "sistema", "sistema")
verificar(app.styleHints().colorScheme() in (Qt.ColorScheme.Light, Qt.ColorScheme.Dark, Qt.ColorScheme.Unknown),
          "sistema devolve a escolha ao Windows")
igual(tema.aplicar(app, "roxo"), "sistema", "modo desconhecido vira sistema")
igual(tema.esquema_de("escuro"), Qt.ColorScheme.Dark, "esquema_de escuro")

# -- a janela: menu, preferencia e abertura em cada tema
j = JanelaPrincipal(ScannerFalso(), configuracao.Configuracao())
verificar(j.acoes_tema["sistema"].isChecked(), "padrao: seguir o sistema")
for modo, esquema in (("escuro", Qt.ColorScheme.Dark), ("claro", Qt.ColorScheme.Light)):
    j.acoes_tema[modo].trigger()
    igual(app.styleHints().colorScheme(), esquema, f"{modo}: esquema aplicado pelo menu")
    igual(configuracao.carregar().tema, modo, f"{modo}: preferencia salva")
    verificar(j.acoes_tema[modo].isChecked(), f"{modo}: item marcado")
    verificar(sum(a.isChecked() for a in j.acoes_tema.values()) == 1, f"{modo}: so' um item marcado")
    app.processEvents()
j.definir_tema("sistema")
igual(configuracao.carregar().tema, "sistema", "voltou ao sistema")
j._salvo = True
j.close()

# -- uma janela nova abre no tema salvo (como o app.py faz)
configuracao.salvar(configuracao.Configuracao(tema="escuro"))
tema.aplicar(app, configuracao.carregar().tema)
igual(app.styleHints().colorScheme(), Qt.ColorScheme.Dark, "tema salvo aplicado na abertura")
j2 = JanelaPrincipal(ScannerFalso())
verificar(j2.acoes_tema["escuro"].isChecked(), "janela nova marca o tema salvo")
j2._salvo = True
j2.close()
tema.aplicar(app, "sistema")

encerrar()
