"""Versao nos tres lugares, preferencias e log."""

import json
import os
import re

from ajudantes import RAIZ, encerrar, igual, pasta_nova, verificar

from digitalizarscan import VERSAO, configuracao

# -- versao: __init__, versao.txt e manifest tem de bater
tupla = tuple(int(x) for x in VERSAO.split("."))
txt = (RAIZ / "versao.txt").read_text(encoding="utf-8")
verificar(f"filevers=({tupla[0]}, {tupla[1]}, {tupla[2]}, 0)" in txt, "versao.txt filevers")
verificar(f"prodvers=({tupla[0]}, {tupla[1]}, {tupla[2]}, 0)" in txt, "versao.txt prodvers")
verificar(f"StringStruct('FileVersion', '{VERSAO}')" in txt, "versao.txt FileVersion")
verificar(f"StringStruct('ProductVersion', '{VERSAO}')" in txt, "versao.txt ProductVersion")
manifesto = (RAIZ / "digitalizarscan.manifest").read_text(encoding="utf-8")
verificar(f'version="{VERSAO}.0"' in manifesto, "manifest tem a versao")
verificar(re.search(rf"^## \[?{re.escape(VERSAO)}", (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8"), re.M),
          "CHANGELOG tem a entrada da versao")

# -- configuracao
os.environ["DIGITALIZARSCAN_CONFIG"] = str(pasta_nova() / "cfg.json")
igual(configuracao.carregar(), configuracao.Configuracao(), "sem arquivo = padrao")
c = configuracao.Configuracao(scanner_id="X", origem="duplex", cor="pb", dpi=600, papel="Ofício",
                              formato="jpg", ocr=False, pasta_saida="C:/tmp",
                              enderecos_escl=["192.0.2.10", "hp.local"])
verificar(configuracao.salvar(c), "salvar")
igual(configuracao.carregar(), c, "ida e volta")
dados = json.loads(configuracao.caminho_do_arquivo().read_text(encoding="utf-8"))
igual(dados["papel"], "Ofício", "acento gravado como esta")

configuracao.caminho_do_arquivo().write_text("{ quebrado", encoding="utf-8")
igual(configuracao.carregar(), configuracao.Configuracao(), "JSON quebrado = padrao")
configuracao.caminho_do_arquivo().write_text(
    '{"dpi": 9999, "cor": "roxo", "ocr": "sim", "x": 1, "origem": "duplex"}', encoding="utf-8")
lido = configuracao.carregar()
igual((lido.dpi, lido.cor, lido.ocr, lido.origem), (300, "cor", True, "duplex"),
      "valores invalidos voltam ao padrao")
configuracao.caminho_do_arquivo().write_text('{"enderecos_escl": ["ok", 3, "  ", null]}', encoding="utf-8")
igual(configuracao.carregar().enderecos_escl, ["ok"], "enderecos invalidos descartados")
configuracao.caminho_do_arquivo().write_text('{"enderecos_escl": "192.0.2.1"}', encoding="utf-8")
igual(configuracao.carregar().enderecos_escl, [], "enderecos de tipo errado")
configuracao.caminho_do_arquivo().write_text("[1, 2]", encoding="utf-8")
igual(configuracao.carregar(), configuracao.Configuracao(), "JSON de tipo errado")

# -- nao deixa temporario para tras
configuracao.salvar(c)
igual([p.name for p in configuracao.caminho_do_arquivo().parent.iterdir()], ["cfg.json"], "sem sobras")

encerrar()
