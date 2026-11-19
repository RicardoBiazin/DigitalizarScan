"""Documento: paginas em disco, girar, reordenar, remover."""

from PIL import Image

from ajudantes import abrir, encerrar, igual, levanta, pasta_nova, verificar

from digitalizarscan.documento import Documento, pasta_temporaria


def imagem(largura, altura, cor="white", modo="RGB"):
    return Image.new(modo, (largura, altura), cor)


doc = Documento(pasta_nova())
a = doc.adicionar(imagem(200, 300, "red"), 150)
b = doc.adicionar(imagem(200, 300, "green", "L"), 150)
c = doc.adicionar(imagem(200, 300, 1, "1"), 150)
igual(len(doc), 3, "3 paginas")
verificar(all(p.caminho.is_file() for p in doc.paginas), "cada pagina em disco")
verificar(all(p.miniatura.startswith(b"\x89PNG") for p in doc.paginas), "miniaturas PNG")
igual([abrir(p.caminho).mode for p in doc.paginas], ["RGB", "L", "1"], "modos preservados")
igual(abrir(a.caminho).info.get("dpi", (0, 0))[0] // 1, 150, "dpi gravado no PNG")

# modo exotico vira RGB
d = doc.adicionar(Image.new("RGBA", (10, 10)), 150)
igual(abrir(d.caminho).mode, "RGB", "RGBA vira RGB")
doc.remover(d.id)

# girar 90 horario troca largura e altura; 4 giros voltam ao original
doc.girar(a.id, 90)
igual(abrir(a.caminho).size, (300, 200), "girou 90")
doc.girar(a.id, 90)
doc.girar(a.id, 90)
doc.girar(a.id, 90)
igual(abrir(a.caminho).size, (200, 300), "4 giros")
doc.girar(a.id, -90)
igual(abrir(a.caminho).size, (300, 200), "anti-horario")
doc.girar(a.id, 90)

# sentido: pixel do canto superior esquerdo vai para o superior direito no giro horario
canto = Documento(pasta_nova())
img = Image.new("RGB", (4, 2), "white")
img.putpixel((0, 0), (255, 0, 0))
p = canto.adicionar(img, 150)
canto.girar(p.id, 90)
girada = abrir(p.caminho)
igual(girada.size, (2, 4), "tamanho apos girar")
igual(girada.getpixel((1, 0)), (255, 0, 0), "giro horario leva o canto sup. esq. para o sup. dir.")

# reordenar
doc.reordenar([c.id, a.id, b.id])
igual([p.id for p in doc.paginas], [c.id, a.id, b.id], "nova ordem")
levanta(ValueError, lambda: doc.reordenar([a.id]), "ordem incompleta")
levanta(ValueError, lambda: doc.reordenar([a.id, b.id, c.id, 99]), "id desconhecido")
igual([p.name for p in doc.caminhos()], [c.caminho.name, a.caminho.name, b.caminho.name], "caminhos na ordem")

# remover
doc.remover(a.id)
igual(len(doc), 2, "removeu")
verificar(not a.caminho.exists(), "arquivo da pagina removida apagado")
levanta(KeyError, lambda: doc.remover(a.id), "remover duas vezes")

# limpar e descartar
doc.limpar()
igual(len(doc), 0, "limpou")
igual(list(doc.pasta.glob("p*.png")), [], "sem PNGs")
doc.adicionar(imagem(10, 10), 150)
doc.descartar()
verificar(not doc.pasta.exists(), "pasta temporaria apagada")

# ids nunca se repetem, mesmo apos remover
novo = Documento(pasta_nova())
x = novo.adicionar(imagem(5, 5), 150)
novo.remover(x.id)
y = novo.adicionar(imagem(5, 5), 150)
verificar(x.id != y.id, "id nao reaproveitado")

# pasta temporaria: ASCII e vazia
t = pasta_temporaria()
verificar(str(t).isascii() and t.is_dir() and not list(t.iterdir()), "pasta temporaria ASCII e vazia")
t.rmdir()

encerrar()
