"""Gera digitalizarscan/recursos/icone.ico (varios tamanhos) com o Pillow.

    .venv\\Scripts\\python.exe ferramentas\\gerar_icone.py

Desenho: quadrado arredondado ardosia, uma folha clara e uma faixa verde-agua que
atravessa a folha (a luz do scanner). Traco grosso de proposito: a 16 px uma forma de
1 px some.
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "digitalizarscan" / "recursos" / "icone.ico"

FUNDO = (0x1E, 0x1F, 0x22, 255)
FOLHA = (0xE8, 0xEA, 0xED, 255)
LINHA = (0x8A, 0x8F, 0x98, 255)
FEIXE = (0x3F, 0xB9, 0x9B, 255)

TAMANHOS = (16, 24, 32, 48, 64, 128, 256)


def desenhar(n: int) -> Image.Image:
    # Desenha em 4x e reduz: bordas suaves sem depender de antialias do ImageDraw.
    g = n * 4
    imagem = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    d = ImageDraw.Draw(imagem)
    d.rounded_rectangle((0, 0, g - 1, g - 1), radius=g // 5, fill=FUNDO)

    esq, dir_, topo, base = g * 0.24, g * 0.76, g * 0.14, g * 0.86
    d.rectangle((esq, topo, dir_, base), fill=FOLHA)
    for i in range(3):                      # linhas de texto
        y = topo + (base - topo) * (0.16 + 0.12 * i)
        d.rectangle((esq + g * 0.07, y, dir_ - g * 0.07 - (g * 0.1 if i == 2 else 0), y + g * 0.035), fill=LINHA)

    y = g * 0.58                            # feixe do scanner, passando da borda da folha
    d.rectangle((g * 0.14, y, g * 0.86, y + g * 0.075), fill=FEIXE)
    return imagem.resize((n, n), Image.LANCZOS)


def main() -> int:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    maior = desenhar(256)
    maior.save(DESTINO, format="ICO", sizes=[(t, t) for t in TAMANHOS],
               append_images=[desenhar(t) for t in TAMANHOS if t != 256])
    print(DESTINO, DESTINO.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
