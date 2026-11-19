"""Scanner via WIA 2.0 (Windows Image Acquisition), pelo COM do Windows.

Nao precisa de driver TWAIN: se o Windows enxerga a multifuncional como
scanner, isto funciona. Todo uso do COM fica neste arquivo.

Constantes de propriedade (documentadas pela Microsoft):
    6146 intencao de cor    6147/6148 DPI horizontal/vertical
    6149/6150 posicao X/Y   6151/6152 largura/altura da area, em pixels
    3074/3075 tamanho maximo do vidro em milesimos de polegada
    3086 capacidades do alimentador   3088 origem escolhida   3096 paginas
"""

from __future__ import annotations

import io
import os
import tempfile
import time
from typing import Any, Callable, Iterator

from PIL import Image

from digitalizarscan import log_interno
from digitalizarscan.i18n import t
from digitalizarscan.scanner.base import (PAPEIS_MM, Capacidades, Dispositivo,
                                          ErroScanner, Opcoes)

log = log_interno.obter(__name__)

P_COR, P_DPI_X, P_DPI_Y = 6146, 6147, 6148
P_POS_X, P_POS_Y, P_LARGURA, P_ALTURA = 6149, 6150, 6151, 6152
P_VIDRO_X, P_VIDRO_Y = 3074, 3075
P_CAPACIDADES, P_ORIGEM, P_PAGINAS = 3086, 3088, 3096
P_STATUS = 3087

#: Bits de 3086/3088.
ALIMENTADOR, VIDRO, DUPLEX = 1, 2, 4
SO_FRENTE = 32          # 0x20, aceito no 3088 de drivers WSD

#: Variantes de configuracao tentadas, em ordem, quando o driver devolve E_INVALIDARG na
#: primeira pagina. Bit 1: alimentador com SO_FRENTE. Bit 2: so' origem, cor e dpi (sem
#: paginas nem area). Cada tentativa parte de uma conexao nova.
VARIANTES = (0, 1, 2, 3)

INTENCAO_COR = {"cor": 1, "cinza": 2, "pb": 4}

FORMATO_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
FORMATO_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"

SEM_PAPEL = 0x80210003
ARGUMENTO_INVALIDO = 0x80070057
OCUPADO, AQUECENDO = 0x80210006, 0x80210007

#: O scanner ocupado (terminando o job anterior, ejetando a folha, aquecendo) nao e' erro: espera
#: e repete. 15 esperas de 2 s = 30 s antes de desistir.
ESPERA_S = 2.0
ESPERAS_MAXIMAS = 15
#: Depois de ao menos uma pagina, o scanner ocupado costuma ser so' o fim do lote (drivers WSD
#: respondem "ocupado" em vez de "sem papel"): espera pouco e encerra sem erro.
ESPERAS_APOS_PAGINA = 3

#: WIA 2.0 separa vidro e alimentador em itens filhos, cada um com a sua categoria.
CATEGORIAS = {"{FB607B1F-43F3-488B-855B-FB703EC342A6}": "vidro",
              "{FE131934-F84C-42AD-8DA4-6129CDDA8B4C}": "alimentador"}
P_NOME_ITEM = 4098

#: Codigos do WIA que tem mensagem propria no catalogo (chave erro.wia.<HEX>).
CODIGOS_CONHECIDOS = {0x80210001, 0x80210002, 0x80210003, 0x80210004, 0x80210005, 0x80210006,
                      0x80210007, 0x80210008, 0x8021000A, 0x8021000D, 0x80210015, 0x80210016,
                      0x80210020}

DISP_E_EXCEPTION = 0x80020009


def codigo_do_erro(exc: BaseException) -> int | None:
    """Extrai o HRESULT do WIA de um `pywintypes.com_error`, ou None."""
    args = getattr(exc, "args", ())
    detalhe = args[2] if len(args) > 2 else None
    # excepinfo[5] guarda o codigo do servidor; args[0] costuma ser so' DISP_E_EXCEPTION.
    candidatos = (detalhe[5] if detalhe and len(detalhe) > 5 else None,
                  args[0] if args else None)
    for candidato in candidatos:
        if isinstance(candidato, int) and candidato:
            valor = candidato & 0xFFFFFFFF
            if valor != DISP_E_EXCEPTION:
                return valor
    return None


def erro_amigavel(exc: BaseException) -> ErroScanner:
    codigo = codigo_do_erro(exc)
    if codigo in CODIGOS_CONHECIDOS:
        return ErroScanner(t(f"erro.wia.{codigo:08X}"))
    if codigo:
        return ErroScanner(t("erro.generico_codigo", codigo=f"{codigo:08X}"))
    return ErroScanner(t("erro.generico"))


def _eh_com_error(exc: BaseException) -> bool:
    return type(exc).__name__ == "com_error"


def _itens(colecao: Any) -> list[Any]:
    """Elementos de uma colecao WIA (indice 1, como o COM define)."""
    return [colecao.Item(i) for i in range(1, int(colecao.Count) + 1)]


def _propriedades(objeto: Any) -> dict[int, Any]:
    return {p.PropertyID: p for p in _itens(objeto.Properties)}


def _definir(props: dict[int, Any], numero: int, valor: int) -> bool:
    """Grava uma propriedade se existir; devolve False se o driver recusou ou nao tem."""
    p = props.get(numero)
    if p is None:
        return False
    try:
        p.Value = int(valor)
        log.info("propriedade %s=%s gravada", numero, valor)
        return True
    except Exception as exc:          # noqa: BLE001 - COM levanta tipos variados
        log.info("propriedade %s=%s recusada: %s", numero, valor, exc)
        return False


def _valores_permitidos(prop: Any) -> list[int] | tuple[int, int] | None:
    """Lista (LIST) ou faixa (min, max) de uma propriedade; None se nao restringe."""
    try:
        tipo = prop.SubType
        if tipo == 3:
            vetor = prop.SubTypeValues
            return [int(vetor.Item(i)) for i in range(1, vetor.Count + 1)]
        if tipo == 2:
            return (int(prop.SubTypeMin), int(prop.SubTypeMax))
    except Exception:                 # noqa: BLE001
        return None
    return None


def _dados_da_imagem(arquivo: Any) -> bytes:
    bruto = arquivo.FileData.BinaryData
    if isinstance(bruto, (bytes, bytearray, memoryview)):
        return bytes(bruto)
    # Outro tipo (depende da versao do pywin32): cai para arquivo temporario.
    pasta = tempfile.mkdtemp(prefix="dscan-wia-")
    caminho = os.path.join(pasta, "pagina.img")
    arquivo.SaveFile(caminho)
    with open(caminho, "rb") as f:
        return f.read()


def _dormir(segundos: float, cancelado: Callable[[], bool]) -> None:
    """Espera em fatias curtas para o botao Cancelar responder."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim and not cancelado():
        time.sleep(min(0.2, max(0.0, fim - time.monotonic())))


def _classificar(item: Any) -> str | None:
    """'vidro' ou 'alimentador' pela categoria (GUID) ou pelo nome do item; None se nao der."""
    try:
        props = _propriedades(item)
    except Exception:                   # noqa: BLE001
        return None
    for p in props.values():
        try:
            valor = str(p.Value).upper()
        except Exception:               # noqa: BLE001
            continue
        if valor in CATEGORIAS:
            return CATEGORIAS[valor]
    nome = ""
    if P_NOME_ITEM in props:
        try:
            nome = str(props[P_NOME_ITEM].Value).lower()
        except Exception:               # noqa: BLE001
            pass
    if "feed" in nome or "alimentador" in nome or "adf" in nome:
        return "alimentador"
    if "flat" in nome or "vidro" in nome:
        return "vidro"
    return None


class ScannerWia:
    def __init__(self, fabrica: Callable[[str], Any] | None = None):
        """`fabrica(progid)` so' existe para os testes injetarem um COM de mentira."""
        self._fabrica = fabrica
        self._com_iniciado = False

    # -- infraestrutura COM ---------------------------------------------------
    def _criar(self, progid: str) -> Any:
        if self._fabrica is not None:
            return self._fabrica(progid)
        import win32com.client
        return win32com.client.Dispatch(progid)

    def preparar_thread(self) -> None:
        if self._fabrica is None:
            import pythoncom
            pythoncom.CoInitialize()
            self._com_iniciado = True

    def encerrar_thread(self) -> None:
        if self._com_iniciado:
            import pythoncom
            pythoncom.CoUninitialize()
            self._com_iniciado = False

    # -- dispositivos ---------------------------------------------------------
    def listar(self) -> list[Dispositivo]:
        try:
            gerente = self._criar("WIA.DeviceManager")
            achados = []
            for info in _itens(gerente.DeviceInfos):
                if int(info.Type) != 1:     # 1 = scanner
                    continue
                achados.append(Dispositivo(str(info.DeviceID), str(info.Properties("Name").Value)))
            return achados
        except Exception as exc:        # noqa: BLE001
            if _eh_com_error(exc):
                raise erro_amigavel(exc) from exc
            raise

    def _conectar(self, dispositivo_id: str) -> Any:
        gerente = self._criar("WIA.DeviceManager")
        for info in _itens(gerente.DeviceInfos):
            if str(info.DeviceID) == dispositivo_id:
                return info.Connect()
        raise ErroScanner(t("erro.scanner_sumiu"))

    def capacidades(self, dispositivo_id: str) -> Capacidades:
        try:
            dispositivo = self._conectar(dispositivo_id)
            itens = _itens(dispositivo.Items)
            classes = {}
            for i in itens:
                classe = _classificar(i)
                if classe and classe not in classes:
                    classes[classe] = i
            props = _propriedades(dispositivo)
            if classes:
                # WIA 2.0: um item filho por origem. O duplex vem das capacidades do item.
                origens = [o for o in ("vidro", "alimentador") if o in classes]
                if "alimentador" in classes:
                    caps = _propriedades(classes["alimentador"]).get(P_CAPACIDADES) or props.get(P_CAPACIDADES)
                    try:
                        if caps is not None and int(caps.Value) & DUPLEX:
                            origens.append("duplex")
                    except Exception:       # noqa: BLE001
                        pass
            else:
                origens = ["vidro"]
                if P_CAPACIDADES in props:
                    bits = int(props[P_CAPACIDADES].Value)
                    origens = [o for o, bit in (("vidro", VIDRO), ("alimentador", ALIMENTADOR))
                               if bits & bit]
                    if bits & ALIMENTADOR and bits & DUPLEX:
                        origens.append("duplex")
                    origens = origens or ["vidro"]
            dpis = (150, 200, 300, 600)
            if itens:
                p = _propriedades(itens[0]).get(P_DPI_X)
                limites = _valores_permitidos(p) if p is not None else None
                if isinstance(limites, list):
                    dpis = tuple(d for d in dpis if d in limites) or dpis
                elif isinstance(limites, tuple):
                    dpis = tuple(d for d in dpis if limites[0] <= d <= limites[1]) or dpis
            vidro_mm = None
            try:
                if P_VIDRO_X in props and P_VIDRO_Y in props:
                    vidro_mm = (int(props[P_VIDRO_X].Value) / 1000 * 25.4,
                                int(props[P_VIDRO_Y].Value) / 1000 * 25.4)
            except Exception:           # noqa: BLE001
                vidro_mm = None
            return Capacidades(origens=tuple(origens), dpis=dpis, vidro_mm=vidro_mm)
        except ErroScanner:
            raise
        except Exception as exc:        # noqa: BLE001
            if _eh_com_error(exc):
                raise erro_amigavel(exc) from exc
            raise

    def previa(self, dispositivo_id: str) -> Image.Image:
        """Vidro inteiro em baixa resolucao (o driver pode ignorar o dpi e mandar mais)."""
        opcoes = Opcoes(origem="vidro", cor="cor", dpi=75, papel="total")
        try:
            dispositivo = self._conectar(dispositivo_id)
            item = self._escolher_item(dispositivo, "vidro")
            self._configurar(dispositivo, item, opcoes)
            return self._transferir(item)
        except ErroScanner:
            raise
        except Exception as exc:        # noqa: BLE001
            if _eh_com_error(exc):
                raise erro_amigavel(exc) from exc
            raise

    def _escolher_item(self, dispositivo: Any, origem: str) -> Any:
        """O item filho da origem pedida; driver de item unico (WIA 1.0) cai no primeiro."""
        itens = _itens(dispositivo.Items)
        if not itens:
            raise ErroScanner(t("erro.sem_item"))
        alvo = "vidro" if origem == "vidro" else "alimentador"
        for item in itens:
            if _classificar(item) == alvo:
                return item
        return itens[0]

    def diagnostico(self, dispositivo_id: str) -> str:
        """Texto com tudo o que o driver expoe: para mandar quando algo nao funciona."""
        linhas = [f"DigitalizarScan - diagnostico do WIA\nDispositivo: {dispositivo_id}"]
        dispositivo = self._conectar(dispositivo_id)

        def despejar(rotulo, objeto):
            linhas.append(f"\n[{rotulo}]")
            for pid, p in sorted(_propriedades(objeto).items()):
                try:
                    extra = ""
                    limites = _valores_permitidos(p)
                    if limites is not None:
                        extra = f"  permitido={limites}"
                    linhas.append(f"{pid:>6} {p.Name} = {p.Value!r}{extra}")
                except Exception as exc:    # noqa: BLE001
                    linhas.append(f"{pid:>6} (ilegivel: {exc})")

        despejar("dispositivo", dispositivo)
        for numero, item in enumerate(_itens(dispositivo.Items), 1):
            despejar(f"item {numero}: {_classificar(item) or 'desconhecido'}", item)
        linhas.append("\n[ultimas linhas do log]")
        try:
            arquivo = log_interno.pasta_de_dados() / "digitalizarscan.log"
            linhas.extend(arquivo.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
        except OSError:
            linhas.append("(sem log)")
        return "\n".join(linhas) + "\n"

    # -- digitalizacao --------------------------------------------------------
    def _configurar(self, dispositivo: Any, item: Any, opcoes: Opcoes, variante: int = 0) -> None:
        """Grava as propriedades da digitalizacao; `variante` esta' descrita em VARIANTES."""
        minimo = bool(variante & 2)
        props_dev = _propriedades(dispositivo)
        props_item = _propriedades(item)

        origem = {"vidro": VIDRO, "alimentador": ALIMENTADOR,
                  "duplex": ALIMENTADOR | DUPLEX}[opcoes.origem]
        if variante & 1 and opcoes.origem == "alimentador":
            origem |= SO_FRENTE
        # WIA 2.0 guarda a origem no item; WIA 1.0, no dispositivo.
        if not _definir(props_item, P_ORIGEM, origem):
            _definir(props_dev, P_ORIGEM, origem)
        if not minimo:
            # Uma folha por transferencia, tambem no alimentador (o loop segue ate' faltar papel):
            # drivers WSD recusam "todas as paginas" (0) com argumento invalido.
            if not _definir(props_item, P_PAGINAS, 1):
                _definir(props_dev, P_PAGINAS, 1)

        _definir(props_item, P_COR, INTENCAO_COR[opcoes.cor])
        _definir(props_item, P_DPI_X, opcoes.dpi)
        _definir(props_item, P_DPI_Y, opcoes.dpi)
        if minimo:
            return

        # A area depende do DPI: so' depois de gravar a resolucao.
        _definir(props_item, P_POS_X, 0)
        _definir(props_item, P_POS_Y, 0)
        largura_max = altura_max = None
        if P_VIDRO_X in props_dev and P_VIDRO_Y in props_dev:
            try:
                largura_max = int(props_dev[P_VIDRO_X].Value) / 1000 * opcoes.dpi
                altura_max = int(props_dev[P_VIDRO_Y].Value) / 1000 * opcoes.dpi
            except Exception:           # noqa: BLE001
                pass
        if opcoes.regiao_mm and opcoes.origem == "vidro":
            # Area escolhida na previa: mm -> pixels do dpi atual, dentro do vidro.
            x, y, larg, alt = (round(v / 25.4 * opcoes.dpi) for v in opcoes.regiao_mm)
            if largura_max:
                x = max(0, min(x, int(largura_max) - 8))
                larg = max(8, min(larg, int(largura_max) - x))
            if altura_max:
                y = max(0, min(y, int(altura_max) - 8))
                alt = max(8, min(alt, int(altura_max) - y))
            _definir(props_item, P_POS_X, x)
            _definir(props_item, P_POS_Y, y)
            _definir(props_item, P_LARGURA, larg)
            _definir(props_item, P_ALTURA, alt)
            return
        medida = PAPEIS_MM.get(opcoes.papel)
        if medida is None:
            if largura_max and altura_max:
                _definir(props_item, P_LARGURA, int(largura_max))
                _definir(props_item, P_ALTURA, int(altura_max))
            return
        largura = round(medida[0] / 25.4 * opcoes.dpi)
        altura = round(medida[1] / 25.4 * opcoes.dpi)
        if largura_max:
            largura = min(largura, int(largura_max))
        if altura_max:
            altura = min(altura, int(altura_max))
        _definir(props_item, P_LARGURA, largura)
        _definir(props_item, P_ALTURA, altura)

    def _status_do_alimentador(self, dispositivo: Any) -> int | None:
        try:
            status = _propriedades(dispositivo).get(P_STATUS)
            return int(status.Value) if status is not None else None
        except Exception:               # noqa: BLE001
            return None

    def _transferir(self, item: Any) -> Image.Image:
        ultimo: Exception | None = None
        for formato in (FORMATO_PNG, FORMATO_BMP):
            try:
                arquivo = item.Transfer(formato)
                imagem = Image.open(io.BytesIO(_dados_da_imagem(arquivo)))
                imagem.load()
                return imagem
            except Exception as exc:    # noqa: BLE001
                if _eh_com_error(exc) and codigo_do_erro(exc) in (SEM_PAPEL, OCUPADO, AQUECENDO):
                    raise           # estados do scanner, nao falha do formato: nao adianta trocar PNG por BMP
                ultimo = exc
                log.info("transferencia em %s falhou: %s", formato, exc)
        assert ultimo is not None
        raise ultimo

    def digitalizar(self, dispositivo_id: str, opcoes: Opcoes,
                    cancelado: Callable[[], bool]) -> Iterator[Image.Image]:
        try:
            dispositivo = self._conectar(dispositivo_id)
            item = self._escolher_item(dispositivo, opcoes.origem)
            self._configurar(dispositivo, item, opcoes)

            entregues = 0
            variante = 0
            esperas = 0
            while not cancelado():
                try:
                    imagem = self._transferir(item)
                except Exception as exc:    # noqa: BLE001
                    codigo = codigo_do_erro(exc) if _eh_com_error(exc) else None
                    if codigo == SEM_PAPEL:
                        if entregues == 0:
                            raise erro_amigavel(exc) from exc
                        return              # acabaram as folhas: fim normal do lote
                    if codigo in (OCUPADO, AQUECENDO):
                        limite = ESPERAS_MAXIMAS if entregues == 0 else ESPERAS_APOS_PAGINA
                        if esperas < limite:
                            esperas += 1
                            log.info("scanner ocupado; espera %s de %s", esperas, limite)
                            _dormir(ESPERA_S, cancelado)
                            continue
                        if entregues > 0:
                            log.info("scanner ainda ocupado apos %s pagina(s): fim do lote", entregues)
                            return
                    if (codigo == ARGUMENTO_INVALIDO and entregues == 0
                            and variante + 1 < len(VARIANTES)):
                        variante += 1
                        log.info("argumento invalido na 1a pagina; tentando a variante %s", VARIANTES[variante])
                        # A tentativa que falhou pode ter deixado o scanner ocupado: da' tempo a ele.
                        _dormir(ESPERA_S, cancelado)
                        # Conexao nova: o que ja' foi gravado no item da conexao anterior sai de cena.
                        dispositivo = self._conectar(dispositivo_id)
                        item = self._escolher_item(dispositivo, opcoes.origem)
                        self._configurar(dispositivo, item, opcoes, VARIANTES[variante])
                        continue
                    raise
                entregues += 1
                esperas = 0
                yield imagem
                if opcoes.origem == "vidro":
                    return
                # So' registra: ainda nao se sabe se o 3087 deste driver e' confiavel para decidir o fim.
                log.info("apos %s pagina(s): 3087 (status do alimentador) = %s", entregues,
                         self._status_do_alimentador(dispositivo))
        except ErroScanner:
            raise
        except Exception as exc:            # noqa: BLE001
            if _eh_com_error(exc):
                raise erro_amigavel(exc) from exc
            raise
