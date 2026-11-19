"""Receita de empacotamento: o .spec e o build.bat apontam para o que existe."""

import re

from ajudantes import RAIZ, encerrar, verificar

spec = (RAIZ / "DigitalizarScan.spec").read_text(encoding="utf-8")
bat = (RAIZ / "build.bat").read_text(encoding="utf-8")

verificar((RAIZ / "digitalizarscan" / "recursos" / "icone.ico").is_file(), "icone.ico existe")
verificar("recursos" in spec and "icone.ico" in spec, ".spec usa o icone")
verificar("versao.txt" in spec and "digitalizarscan.manifest" in spec, ".spec usa versao.txt e o manifest")
verificar("console=False" in spec, ".spec gera executavel sem console")
for modulo in ("win32com.client", "pythoncom", "pywintypes"):
    verificar(modulo in spec, f".spec declara {modulo} (carregado por nome em tempo de execucao)")
verificar("tesseract" in spec, ".spec embute a pasta tesseract")
for codigo in ("pt", "en", "es", "zh"):
    verificar(f"digitalizarscan.idiomas.{codigo}" in spec, f".spec declara o catalogo {codigo} (importado em i18n.py)")
for qm in ("qtbase_es.qm", "qtbase_zh_CN.qm", "qtbase_pt_BR.qm"):
    verificar(qm in spec, f".spec empacota {qm}")
verificar('"pypdf"' in spec, ".spec exclui o pypdf (so' de teste)")

# o build tem as 5 etapas, na ordem, e a suite roda antes de empacotar
posicoes = [bat.find(f"[{i}/5]") for i in range(1, 6)]
verificar(all(p >= 0 for p in posicoes) and posicoes == sorted(posicoes), "build.bat com 5 etapas em ordem")
verificar(bat.find("rodar_todos.py") < bat.find("PyInstaller --noconfirm"), "suite roda antes do PyInstaller")
verificar("--autoverificacao" in bat and "fumaca_exe.py" in bat, "build.bat confere o executavel")
verificar(".venv\\Scripts\\python.exe" in bat, "build.bat usa o python do .venv")
verificar((RAIZ / "build.bat").read_bytes().count(b"\r\n") > 50, "build.bat com fim de linha CRLF")

# modulos excluidos nao podem ser os que o programa usa
usados = set()
for arquivo in (RAIZ / "digitalizarscan").rglob("*.py"):
    usados.update(re.findall(r"^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)", arquivo.read_text(encoding="utf-8"), re.M))
excluidos = re.search(r"EXCLUDES = \[(.*?)\]", spec, re.S).group(1)
for modulo in re.findall(r'"([^"]+)"', excluidos):
    verificar(modulo not in usados, f"o programa importa {modulo}, que o .spec exclui")

encerrar()
