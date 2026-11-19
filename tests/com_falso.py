"""COM do WIA de mentira, so' o bastante para exercitar `ScannerWia` sem hardware."""

from __future__ import annotations

import io

import pywintypes
from PIL import Image

SEM_PAPEL = -2145320957          # 0x80210003 como inteiro com sinal, como o COM entrega
OCUPADO = -2145320954            # 0x80210006
COMUNICACAO = -2145320950        # 0x8021000A
ARGUMENTO_INVALIDO = -2147024809  # 0x80070057 (E_INVALIDARG)

CAT_VIDRO = "{FB607B1F-43F3-488B-855B-FB703EC342A6}"
CAT_ALIMENTADOR = "{FE131934-F84C-42AD-8DA4-6129CDDA8B4C}"


def erro_com(scode: int) -> pywintypes.com_error:
    return pywintypes.com_error(-2147352567, "Exceção.", (0, None, "", None, 0, scode), None)


class Colecao:
    def __init__(self, itens):
        self._itens = list(itens)
        self.Count = len(self._itens)

    def Item(self, i):
        return self._itens[i - 1]


class Vetor(Colecao):
    pass


class Propriedade:
    def __init__(self, id_, valor, tipo=1, minimo=0, maximo=0, valores=None, recusa=False):
        self.PropertyID = id_
        self._valor = valor
        self.SubType = tipo
        self.SubTypeMin = minimo
        self.SubTypeMax = maximo
        self.SubTypeValues = Vetor(valores or [])
        self._recusa = recusa
        self.gravacoes: list = []

    @property
    def Value(self):
        return self._valor

    @Value.setter
    def Value(self, v):
        if self._recusa:
            raise erro_com(-2145320954)
        self.gravacoes.append(v)
        self._valor = v


def png(largura=20, altura=30) -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), "white").save(saida, "PNG")
    return saida.getvalue()


class _Dados:
    def __init__(self, dados):
        self.BinaryData = dados


class _Arquivo:
    def __init__(self, dados):
        self.FileData = _Dados(dados)


class Item:
    def __init__(self, folhas=1, propriedades=None, falha_png=False, erro_inicial=None,
                 categoria=None, nome=None, exige_minimo=False, capacidades=None, exige_origem=None, ocupado_vezes=0, fim_ocupado=False):
        base = propriedades if propriedades is not None else [
            Propriedade(6146, 1), Propriedade(6147, 150, tipo=3, valores=[100, 150, 300]),
            Propriedade(6148, 150), Propriedade(6149, 0), Propriedade(6150, 0),
            Propriedade(6151, 0), Propriedade(6152, 0), Propriedade(3088, 0), Propriedade(3096, 1)]
        if categoria:
            base = base + [Propriedade(4120, categoria)]
        if nome:
            base = base + [Propriedade(4098, nome)]
        if capacidades is not None:
            base = base + [Propriedade(3086, capacidades)]
        self.Properties = Colecao(base)
        self.exige_minimo = exige_minimo
        self.exige_origem = exige_origem
        self.ocupado_vezes = ocupado_vezes
        self.fim_ocupado = fim_ocupado
        self.folhas = folhas
        self.formatos: list[str] = []
        self.falha_png = falha_png
        self.erro_inicial = erro_inicial

    def prop(self, id_):
        return next(p for p in self.Properties._itens if p.PropertyID == id_)

    def Transfer(self, formato):
        self.formatos.append(formato)
        if self.erro_inicial is not None:
            raise erro_com(self.erro_inicial)
        if self.ocupado_vezes > 0:
            self.ocupado_vezes -= 1
            raise erro_com(OCUPADO)
        if self.exige_origem is not None:
            gravada = [g for p in self.Properties._itens if p.PropertyID == 3088 for g in p.gravacoes]
            if not gravada or gravada[-1] != self.exige_origem:
                raise erro_com(ARGUMENTO_INVALIDO)
        if self.exige_minimo and any(p.gravacoes for p in self.Properties._itens
                                     if p.PropertyID in (3096, 6151, 6152)):
            raise erro_com(ARGUMENTO_INVALIDO)
        if self.falha_png and formato == "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}":
            raise erro_com(-2145320959)
        if self.folhas <= 0:
            raise erro_com(OCUPADO if self.fim_ocupado else SEM_PAPEL)
        self.folhas -= 1
        return _Arquivo(png())


class Dispositivo:
    def __init__(self, item, capacidades=7, vidro=(8500, 11690)):
        self.Items = Colecao(item if isinstance(item, list) else [item])
        self.Properties = Colecao([Propriedade(3086, capacidades), Propriedade(3088, 2),
                                   Propriedade(3096, 1), Propriedade(3074, vidro[0]),
                                   Propriedade(3075, vidro[1])])

    def prop(self, id_):
        return next(p for p in self.Properties._itens if p.PropertyID == id_)


class _Nome:
    def __init__(self, nome):
        self.Value = nome


class Info:
    def __init__(self, id_, nome, dispositivo, tipo=1):
        self.DeviceID = id_
        self.Type = tipo
        self._nome = nome
        self._dispositivo = dispositivo

    def Properties(self, nome):
        assert nome == "Name"
        return _Nome(self._nome)

    def Connect(self):
        # Conexao nova = itens com os valores de fabrica (as gravacoes da conexao anterior somem).
        for item in self._dispositivo.Items._itens:
            for prop in item.Properties._itens:
                prop.gravacoes.clear()
        return self._dispositivo


class Gerente:
    def __init__(self, infos, erro=None):
        if erro is not None:
            raise erro_com(erro)
        self.DeviceInfos = Colecao(infos)


def fabrica_para(*infos, erro=None):
    def fabrica(progid):
        assert progid == "WIA.DeviceManager"
        return Gerente(infos, erro)
    return fabrica
