"""Roda todas as suites e resume o resultado.

    .venv\\Scripts\\python.exe tests\\rodar_todos.py

Sem pytest, de proposito: cada suite roda num processo separado, entao um
travamento de Qt numa suite nao leva as outras junto.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))

#: Teto por suite. Um dialogo modal sem ninguem para clicar travaria a rodada inteira.
LIMITE_POR_SUITE_S = 240

SUITES = [
    ("teste_base.py", "versao nos tres lugares, CHANGELOG e preferencias"),
    ("teste_higiene.py", "sem eval/exec/pickle/shell=True; dependencias fixas; avisos de terceiros"),
    ("teste_documento.py", "paginas em disco: girar, reordenar, remover, limpar"),
    ("teste_saida.py", "PDF, JPG/PNG, nomes e gravacao atomica"),
    ("teste_wia.py", "scanner WIA contra um COM de mentira: alimentador, erros, cancelar"),
    ("teste_escl.py", "eSCL contra servidor HTTP local: 8 folhas do alimentador, duplex, vidro, cancelar"),
    ("teste_descoberta.py", "mDNS: leitura de resposta DNS com compressao; portas de impressora"),
    ("teste_idiomas.py", "4 idiomas: catalogos completos, deteccao do sistema, troca na janela, OCR por idioma"),
    ("teste_tema.py", "tema sistema/claro/escuro: esquema de cor e preferencia"),
    ("teste_previa.py", "previa do vidro com area, estado do alimentador, janela de previa"),
    ("teste_ocr.py", "OCR real com o Tesseract (pula se nao estiver na pasta tesseract)"),
    ("teste_janela.py", "janela: digitalizar, editar paginas, salvar, preferencias, fechar"),
    ("teste_cli.py", "linha de comando e autoverificacao"),
    ("teste_empacotamento.py", "build em cinco etapas; .spec aponta para o que existe"),
]


def main() -> int:
    python = sys.executable
    falhas = []
    inicio = time.monotonic()
    for nome, descricao in SUITES:
        print(f"-- {nome}: {descricao}", flush=True)
        t0 = time.monotonic()
        try:
            r = subprocess.run([python, "-X", "utf8", os.path.join(AQUI, nome)], cwd=AQUI,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=LIMITE_POR_SUITE_S)
            saida, codigo = (r.stdout + r.stderr).strip(), r.returncode
        except subprocess.TimeoutExpired:
            saida, codigo = f"TEMPO ESGOTADO ({LIMITE_POR_SUITE_S} s)", 1
        ultima = saida.splitlines()[-1] if saida else ""
        print(f"   {'OK ' if codigo == 0 else 'FALHOU'} ({time.monotonic() - t0:.1f} s) {ultima}", flush=True)
        if codigo != 0:
            falhas.append(nome)
            print(saida[-3000:], flush=True)
    print(f"\n{len(SUITES) - len(falhas)}/{len(SUITES)} suites ok em {time.monotonic() - inicio:.0f} s")
    if falhas:
        print("FALHARAM:", ", ".join(falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
