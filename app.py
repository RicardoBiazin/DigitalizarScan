"""DigitalizarScan: digitalizacao pela impressora multifuncional.

    python app.py                    abre a janela
    python app.py --demo             usa um scanner de mentira (sem hardware)
    python app.py --autoverificacao  prova de vida do executavel, sem janela
    python app.py --versao           imprime a versao

--autoverificacao importa tudo o que o .exe precisa (Qt, COM do Windows, Pillow),
gera um PDF de verdade com o scanner de mentira e confere o resultado. O build.bat
roda isto logo depois de empacotar: um modulo esquecido no .spec aparece aqui, e
nao na mao do usuario.
"""

from __future__ import annotations

import os
import sys
import tempfile


def _imprimir(texto: str) -> None:
    if sys.stdout is not None:
        print(texto)


def autoverificacao() -> int:
    import pathlib

    from digitalizarscan import VERSAO, documento, exportar
    from digitalizarscan.saida import ocr
    from digitalizarscan.scanner.base import Opcoes
    from digitalizarscan.scanner.falso import ScannerFalso

    import PySide6.QtWidgets  # noqa: F401  (a janela precisa dele)
    import ssl  # noqa: F401  (eSCL por https)
    from digitalizarscan.scanner import composto, descoberta, escl  # noqa: F401
    descoberta.portas_de_impressora()
    escl.ler_capacidades(b'<x/>')
    from PIL import Image

    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            win32com.client.Dispatch("WIA.DeviceManager")
        finally:
            pythoncom.CoUninitialize()
        com = "WIA ok"
    except Exception as exc:                 # noqa: BLE001
        _imprimir(f"FALHA: COM/WIA indisponivel: {exc}")
        return 1

    scanner = ScannerFalso(folhas_no_alimentador=2)
    opcoes = Opcoes(origem="alimentador", dpi=150)
    doc = documento.Documento()
    try:
        for imagem in scanner.digitalizar("falso-0", opcoes, lambda: False):
            doc.adicionar(imagem, opcoes.dpi)
        if len(doc) != 2:
            _imprimir("FALHA: o scanner de teste nao entregou 2 paginas")
            return 1
        destino = pathlib.Path(tempfile.mkdtemp(prefix="dscan-av-")) / "teste.pdf"
        arquivos, aviso = exportar.exportar(doc.caminhos(), destino, "pdf", 150, False, None)
        dados = arquivos[0].read_bytes()
        if not dados.startswith(b"%PDF") or dados.count(b"/Type /Page") < 2:
            _imprimir("FALHA: o PDF gerado e' invalido")
            return 1
        Image.open(doc.caminhos()[0]).close()
    finally:
        doc.descartar()
    from digitalizarscan import i18n, tema  # noqa: F401
    for codigo in i18n.IDIOMAS:
        catalogo = i18n.catalogo(codigo)
        if len(catalogo) < 100 or catalogo.keys() != i18n.catalogo("pt").keys():
            _imprimir(f"FALHA: catalogo {codigo} incompleto ({len(catalogo)} textos)")
            return 1
    tesseract = ocr.localizar()
    _imprimir(f"OK DigitalizarScan {VERSAO}: {com}; PDF gerado; "
              f"Tesseract: {'sim (' + '+'.join(tesseract.idiomas) + ')' if tesseract else 'nao encontrado'}")
    return 0


def main(argv: list[str]) -> int:
    if "--versao" in argv:
        from digitalizarscan import VERSAO
        _imprimir(VERSAO)
        return 0
    if "--autoverificacao" in argv:
        return autoverificacao()

    from digitalizarscan import configuracao, i18n, idioma, log_interno, tema
    log_interno.iniciar()
    config = configuracao.carregar()
    efetivo = i18n.definir_idioma(config.idioma)

    from PySide6.QtWidgets import QApplication
    from digitalizarscan.interface.janela_principal import JanelaPrincipal

    aplicacao = QApplication(sys.argv[:1])
    aplicacao.setApplicationName("DigitalizarScan")
    idioma.instalar(aplicacao, efetivo)
    tema.aplicar(aplicacao, config.tema)

    if "--demo" in argv:
        from digitalizarscan.scanner.falso import ScannerFalso
        scanner = ScannerFalso(folhas_no_alimentador=3)
    else:
        from digitalizarscan.scanner import descoberta
        from digitalizarscan.scanner.composto import ScannerComposto
        from digitalizarscan.scanner.escl import ScannerEscl
        from digitalizarscan.scanner.wia import ScannerWia
        escl = ScannerEscl(enderecos=lambda: configuracao.carregar().enderecos_escl,
                           descobrir=descoberta.descobrir)
        scanner = ScannerComposto(ScannerWia(), escl)

    janela = JanelaPrincipal(scanner, config)
    janela.show()
    janela.atualizar_scanners()
    return aplicacao.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
