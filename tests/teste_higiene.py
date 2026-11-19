"""Higiene do codigo: nada de execucao dinamica, dependencias fixas, avisos de terceiros."""

import hashlib
import re

from ajudantes import RAIZ, encerrar, verificar

PROIBIDO = [
    (r"(?<![\w.])eval\(", "eval"),
    (r"(?<![\w.])exec\(", "exec"),       # `.exec()` do Qt (loop de eventos, dialogo) e' outra coisa
    (r"\bpickle\b", "pickle"),
    (r"\bmarshal\b", "marshal"),
    (r"shell\s*=\s*True", "shell=True"),
    (r"\bos\.system\(", "os.system"),
    (r"\bos\.popen\(", "os.popen"),
]

for pasta in ("digitalizarscan", "app.py", "ferramentas"):
    alvo = RAIZ / pasta
    arquivos = [alvo] if alvo.is_file() else sorted(alvo.rglob("*.py"))
    for arquivo in arquivos:
        texto = arquivo.read_text(encoding="utf-8")
        for padrao, nome in PROIBIDO:
            achados = [m for m in re.finditer(padrao, texto)]
            verificar(not achados, f"{arquivo.relative_to(RAIZ)} usa {nome}")

# os.startfile so' abre arquivo/pasta que o proprio programa acabou de gravar ou do seu temporario
usos = [a for a in (RAIZ / "digitalizarscan").rglob("*.py") if "os.startfile" in a.read_text(encoding="utf-8")]
verificar([u.name for u in usos] == ["janela_principal.py"], f"os.startfile so' na janela: {[u.name for u in usos]}")

# dependencias de execucao fixas com ==
for arquivo in ("requirements.txt", "requirements-dev.txt"):
    for linha in (RAIZ / arquivo).read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", "-r")):
            continue
        verificar("==" in linha, f"{arquivo}: {linha!r} sem versao fixa")

# toda dependencia de execucao tem aviso de terceiros
avisos = (RAIZ / "AVISOS_DE_TERCEIROS.md").read_text(encoding="utf-8").lower()
for linha in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines():
    if linha.strip() and not linha.startswith("#"):
        nome = re.split(r"[=<>]", linha)[0].strip().lower().replace("-essentials", "")
        verificar(nome in avisos, f"AVISOS_DE_TERCEIROS.md nao cita {nome}")
verificar("tesseract" in avisos, "AVISOS_DE_TERCEIROS.md nao cita o Tesseract")

# nenhuma digitalizacao no repositorio e a pasta do Tesseract fora do git
gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
for item in ("*.pdf", "*.jpg", "tesseract/", ".venv/"):
    verificar(item in gitignore, f".gitignore sem {item}")

# texto de interface em portugues com acento: sem mojibake
for arquivo in (RAIZ / "digitalizarscan").rglob("*.py"):
    texto = arquivo.read_text(encoding="utf-8")
    verificar("Ã" not in texto and "�" not in texto, f"{arquivo.name} com texto corrompido")


# nada pessoal no repositorio publico: IP privado, nome/serial de equipamento, caminho de usuario, e-mail
PRIVADOS = re.compile(r"\b(?:10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)\b")
# Palavras proibidas (nome/serial de equipamento, conta de usuario, dominio da empresa) guardadas como
# SHA-256: o proprio teste nao pode conter o que proibe. Cada arquivo e' quebrado em palavras
# ([A-Za-z0-9_]+) e cada palavra, em minusculas, e' comparada com estes hashes.
HASHES_PROIBIDOS = {
    "08e6a7622b9990dafe1ea0542f7c07c8f96826126815c9726e6b4a105ed90a0d",
    "1582816bef6118a9e717b043c7688e97f34a1471e4c0f3b38a7053719567b4eb",
    "23349c835b55067e60b0b85d6ac89fed0f68abd28da2865ad5f50a0d2a6edca3",
    "254c5786da9694cff9b1056f1ac143142c95fecc868d4f48e8b6ffc61cec9f2f",
    "2a0b1d6f0d378c43250bea85be5b9f485c1b1f5dadb0e6a98e5184aecf40b59d",
    "4a494098e08e44fbe2602c32a23edc2b004b20c15d79d523d1588ea5212aa385",
    "772e5cb4367a32195d048fdb015067460bd44230b8c6614c2239c5eca9c18297",
}
TEXTOS_PROIBIDOS = ("\\Users\\", "@gmail.", "@hotmail.", "@outlook.")
IGNORAR = {".venv", "dist", "build", "tesseract", "__pycache__", ".git"}
EXTENSOES = {".py", ".md", ".txt", ".ps1", ".bat", ".spec", ".manifest", ".json", ".yml", ".yaml"}
for arquivo in sorted(RAIZ.rglob("*")):
    partes = set(arquivo.relative_to(RAIZ).parts)
    if (not arquivo.is_file() or partes & IGNORAR or arquivo.suffix not in EXTENSOES
            or arquivo.name == "teste_higiene.py"):
        continue
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    achado = PRIVADOS.search(texto)
    verificar(achado is None, f"{arquivo.relative_to(RAIZ)}: IP de rede privada ({achado.group(0) if achado else ''})")
    achadas = {w for w in re.findall(r"[A-Za-z0-9_]+", texto)
               if hashlib.sha256(w.lower().encode()).hexdigest() in HASHES_PROIBIDOS}
    verificar(not achadas, f"{arquivo.relative_to(RAIZ)}: palavra proibida (dado pessoal) encontrada")
    for proibido in TEXTOS_PROIBIDOS:
        verificar(proibido not in texto, f"{arquivo.relative_to(RAIZ)}: contem {proibido!r}")

# licenca MIT presente e citada
verificar((RAIZ / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"), "LICENSE MIT")
for readme in ("README.md", "README.en.md", "README.es.md", "README.zh-CN.md"):
    corpo = (RAIZ / readme).read_text(encoding="utf-8")
    verificar("MIT" in corpo, f"{readme} cita a licenca")
    for outro in ("README.md", "README.en.md", "README.es.md", "README.zh-CN.md"):
        if outro != readme:
            verificar(outro in corpo, f"{readme} liga para {outro}")

encerrar()
