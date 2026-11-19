"""Linha de comando: --versao e --autoverificacao rodam sem janela."""

import subprocess
import sys

from ajudantes import RAIZ, encerrar, igual, verificar

from digitalizarscan import VERSAO


def rodar(*args):
    return subprocess.run([sys.executable, "-X", "utf8", str(RAIZ / "app.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


r = rodar("--versao")
igual((r.returncode, r.stdout.strip()), (0, VERSAO), "--versao")

r = rodar("--autoverificacao")
igual(r.returncode, 0, f"--autoverificacao sai com 0: {r.stdout} {r.stderr}")
verificar(r.stdout.startswith(f"OK DigitalizarScan {VERSAO}"), f"saida da autoverificacao: {r.stdout!r}")
verificar("WIA ok" in r.stdout and "PDF gerado" in r.stdout, "autoverificacao confere COM e PDF")

encerrar()
