"""Idiomas: catalogos completos e coerentes, deteccao do sistema, troca na janela, OCR por idioma."""

import ast
import os
import re
import tempfile
import pathlib

from ajudantes import RAIZ, encerrar, igual, verificar

from digitalizarscan import configuracao, i18n
from digitalizarscan.saida import ocr

# -- os 4 catalogos: mesmas chaves, mesmos {marcadores}, nada vazio
catalogos = {c: i18n.catalogo(c) for c in i18n.IDIOMAS}
referencia = catalogos["pt"]
for codigo, cat in catalogos.items():
    faltando = sorted(set(referencia) - set(cat))
    sobrando = sorted(set(cat) - set(referencia))
    verificar(not faltando, f"{codigo}: chaves que faltam {faltando[:5]}")
    verificar(not sobrando, f"{codigo}: chaves que sobram {sobrando[:5]}")
    for chave, texto in cat.items():
        verificar(isinstance(texto, str) and texto.strip(), f"{codigo}.{chave} vazio")
        if chave in referencia:
            igual(sorted(re.findall(r"\{(\w+)\}", texto)), sorted(re.findall(r"\{(\w+)\}", referencia[chave])),
                  f"{codigo}.{chave}: marcadores diferentes do pt")

# -- traduzido de verdade: chines com ideogramas; en/es diferem do pt na maior parte
cjk = re.compile(r"[一-鿿]")
sem_cjk = [k for k, v in catalogos["zh"].items() if not cjk.search(v)]
verificar(len(sem_cjk) <= 25, f"zh: textos sem ideograma demais: {sem_cjk[:8]}")
for codigo in ("en", "es"):
    iguais = [k for k in referencia if catalogos[codigo][k] == referencia[k]]
    verificar(len(iguais) < len(referencia) * 0.20, f"{codigo}: {len(iguais)} textos iguais ao pt: {iguais[:8]}")
verificar(all("0x{codigo}" in catalogos[c]["erro.generico_codigo"] for c in i18n.IDIOMAS), "codigo hex nos 4 idiomas")

# -- atalhos de menu (&) nao repetem dentro do mesmo menu (so' o menu "Arquivo" e o resto tem teclas proprias)
for codigo, cat in catalogos.items():
    barra = [cat[k] for k in ("menu.arquivo", "menu.exibir", "menu.ajuda")]
    letras = [m.group(1).lower() for m in (re.search(r"&(\w)", s) for s in barra) if m]
    verificar(len(letras) == len(set(letras)), f"{codigo}: atalhos repetidos na barra de menus {barra}")
    itens = [cat[k] for k in ("menu.digitalizar", "menu.salvar", "menu.sair")]
    letras = [m.group(1).lower() for m in (re.search(r"&(\w)", s) for s in itens) if m]
    verificar(len(letras) == len(set(letras)), f"{codigo}: atalhos repetidos no menu Arquivo {itens}")

# -- t(): idioma atual, reserva no pt, chave desconhecida, marcador faltando
igual(i18n.idioma_atual(), "pt", "padrao pt")
igual(i18n.t("tela.pagina", n=3), "Página 3", "t com marcador")
igual(i18n.definir_idioma("en"), "en", "definir en")
igual(i18n.t("tela.pagina", n=3), "Page 3", "t em ingles")
igual(i18n.definir_idioma("zh"), "zh", "definir zh")
igual(i18n.t("tela.pagina", n=3), "第 3 页", "t em chines")
igual(i18n.definir_idioma("klingon"), "pt", "idioma desconhecido volta ao pt")
igual(i18n.t("chave.que.nao.existe"), "chave.que.nao.existe", "chave desconhecida volta como esta")
igual(i18n.t("tela.pagina"), "Página {n}", "marcador faltando nao explode")
igual(i18n.t("tela.pagina", n=1, extra="x"), "Página 1", "valor a mais e' ignorado")
i18n.definir_idioma("es")
igual(i18n.t("tela.digitalizar"), "Escanear", "es")
i18n.definir_idioma("pt")

# -- deteccao do sistema (Windows LANGID e nome de locale)
igual(i18n.detectar(0x0416), "pt", "pt-BR")
igual(i18n.detectar(0x0816), "pt", "pt-PT")
igual(i18n.detectar(0x0409), "en", "en-US")
igual(i18n.detectar(0x0C0A), "es", "es-ES")
igual(i18n.detectar(0x080A), "es", "es-MX")
igual(i18n.detectar(0x0804), "zh", "zh-CN")
igual(i18n.detectar(0x0404), "zh", "zh-TW cai no chines")
igual(i18n.detectar(0x0407), "en", "alemao cai no ingles")
igual(i18n.detectar(nome_locale="es_AR.UTF-8"), "es", "locale es_AR")
igual(i18n.detectar(nome_locale="zh-CN"), "zh", "locale zh-CN")
igual(i18n.detectar(nome_locale="fr_FR"), "en", "frances cai no ingles")
verificar(i18n.detectar() in i18n.IDIOMAS, "detectar() do sistema devolve um idioma suportado")
igual(i18n.definir_idioma("auto"), i18n.detectar(), "auto = idioma do sistema")
i18n.definir_idioma("pt")

# -- configuracao: idioma e tema validados
c = configuracao.Configuracao(idioma="xx", tema="roxo").validar()
igual((c.idioma, c.tema), ("auto", "sistema"), "idioma/tema invalidos voltam ao padrao")

# -- OCR segue o idioma da interface (com um Tesseract de mentira: so' as pastas e arquivos)
falso = pathlib.Path(tempfile.mkdtemp(prefix="dscan-tess-")) / "tesseract"
(falso / "tessdata").mkdir(parents=True)
(falso / "tesseract.exe").write_bytes(b"")
for modelo in ("eng", "por", "spa", "chi_sim"):
    (falso / "tessdata" / f"{modelo}.traineddata").write_bytes(b"x")
os.environ["DIGITALIZARSCAN_TESSERACT"] = str(falso / "tesseract.exe")
igual(ocr.localizar("pt").idiomas, ("por", "eng"), "OCR pt")
igual(ocr.localizar("en").idiomas, ("eng",), "OCR en")
igual(ocr.localizar("es").idiomas, ("spa", "eng"), "OCR es")
igual(ocr.localizar("zh").idiomas, ("chi_sim", "eng"), "OCR zh")
(falso / "tessdata" / "spa.traineddata").unlink()
igual(ocr.localizar("es").idiomas, ("eng",), "sem o modelo es: usa o que houver")
for modelo in ("eng", "por", "chi_sim"):
    (falso / "tessdata" / f"{modelo}.traineddata").unlink()
sem_modelos = ocr.localizar("es")
verificar(sem_modelos is None or sem_modelos.exe != falso / "tesseract.exe",
          "sem nenhum modelo nesta pasta: ela nao serve (cai na proxima instalacao, se houver)")
del os.environ["DIGITALIZARSCAN_TESSERACT"]

# -- a janela: troca de idioma muda os textos na hora e fica salva
from PySide6.QtWidgets import QApplication   # noqa: E402
from digitalizarscan.interface.janela_principal import JanelaPrincipal   # noqa: E402
from digitalizarscan.scanner.falso import ScannerFalso   # noqa: E402

app = QApplication([])
JanelaPrincipal.INTERVALO_ESTADO_MS = 0
j = JanelaPrincipal(ScannerFalso(), configuracao.Configuracao())
j._tesseract = None
j.show()
igual(j.botao_digitalizar.text(), "Digitalizar", "janela abre em pt")
igual(j.menu_arquivo.title(), "&Arquivo", "menu em pt")
verificar(j.acoes_idioma["auto"].isChecked(), "Automatico marcado por padrao")

for codigo, digitalizar, origem_vidro, arquivo in (
        ("en", "Scan", "Glass (one page at a time)", "&File"),
        ("es", "Escanear", "Cristal (una página cada vez)", "&Archivo"),
        ("zh", "扫描", "玻璃板（每次一页）", "文件(&F)"),
        ("pt", "Digitalizar", "Vidro (uma página por vez)", "&Arquivo")):
    j.definir_idioma(codigo)
    igual(i18n.idioma_atual(), codigo, f"{codigo}: idioma atual")
    igual(j.botao_digitalizar.text(), digitalizar, f"{codigo}: botao Digitalizar")
    igual(j.combo_origem.itemText(j.combo_origem.findData("vidro")), origem_vidro, f"{codigo}: item do combo")
    igual(j.menu_arquivo.title(), arquivo, f"{codigo}: menu")
    igual(configuracao.carregar().idioma, codigo, f"{codigo}: preferencia salva")
    verificar(j.acoes_idioma[codigo].isChecked(), f"{codigo}: item marcado no menu")
    igual(j.combo_origem.currentData(), "vidro", f"{codigo}: a escolha do combo sobrevive a troca")

# o nome dos idiomas no menu nao depende do idioma atual
j.definir_idioma("zh")
igual([j.acoes_idioma[c].text() for c in ("pt", "en", "es", "zh")], ["Português", "English", "Español", "中文"],
      "nomes dos idiomas fixos")
# paginas ja' na lista tambem mudam
from PIL import Image   # noqa: E402
j.definir_idioma("pt")
pagina = j._documento.adicionar(Image.new("RGB", (40, 60), "white"), 150)
j._acrescentar_item(pagina)
igual(j.lista.item(0).text(), "Página 1", "miniatura em pt")
j.definir_idioma("en")
igual(j.lista.item(0).text(), "Page 1", "miniatura passa para en")
j.definir_idioma("auto")
igual(configuracao.carregar().idioma, "auto", "auto volta a ser gravado")
j.definir_idioma("pt")
j._salvo = True
j.close()

# -- higiene: nenhum texto de tela em portugues "solto" nos modulos (tudo passa pelo catalogo)
ACENTOS = re.compile("[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÇ]")
PERMITIDOS = {"Ofício"}          # valor guardado na configuracao, nao texto de tela
modulos = ["janela_principal.py", "dialogo_previa.py"]
for nome in ("exportar.py", "trabalho.py"):
    modulos.append(nome)
alvos = [RAIZ / "digitalizarscan" / "interface" / "janela_principal.py",
         RAIZ / "digitalizarscan" / "interface" / "dialogo_previa.py",
         RAIZ / "digitalizarscan" / "exportar.py", RAIZ / "digitalizarscan" / "trabalho.py",
         RAIZ / "digitalizarscan" / "saida" / "ocr.py", RAIZ / "digitalizarscan" / "scanner" / "wia.py",
         RAIZ / "digitalizarscan" / "scanner" / "escl.py", RAIZ / "digitalizarscan" / "scanner" / "composto.py",
         RAIZ / "digitalizarscan" / "scanner" / "falso.py", RAIZ / "digitalizarscan" / "scanner" / "base.py"]
for arquivo in alvos:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    docstrings = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and no.body:
            primeiro = no.body[0]
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                docstrings.add(id(primeiro.value))
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docstrings
                and ACENTOS.search(no.value) and no.value not in PERMITIDOS):
            verificar(False, f"{arquivo.name}:{no.lineno}: texto com acento fora do catalogo: {no.value[:50]!r}")

encerrar()
