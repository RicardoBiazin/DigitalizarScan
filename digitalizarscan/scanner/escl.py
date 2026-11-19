"""Scanner pela rede via eSCL (AirScan / Mopria): HTTP puro, sem driver.

Por que existe: na HP OfficeJet Pro 7740 o driver WSD do Windows so' entrega a PRIMEIRA folha do
alimentador pela camada de automacao do WIA (`Item.Transfer`); as demais ficam presas num job
que ninguem baixa, e o scanner responde "ocupado". O eSCL foi feito para isto: um job, e cada
GET em NextDocument devolve uma pagina, ate' 404 (acabou).

    GET  {base}/ScannerCapabilities      fontes, resolucoes, tamanho maximo
    GET  {base}/ScannerStatus            estado e papel no alimentador
    POST {base}/ScanJobs                 cria o job (201 + Location)
    GET  {job}/NextDocument              uma pagina (200), fim (404), ainda nao (503)
    DELETE {job}                         cancela

`base` e' algo como http://192.0.2.10/eSCL. HTTPS da impressora usa certificado
autoassinado: a conexao e' cifrada mas o certificado nao e' conferido (dispositivo da rede local).
"""

from __future__ import annotations

import io
import ipaddress
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

from PIL import Image, ImageFile

from digitalizarscan import log_interno
from digitalizarscan.i18n import t
from digitalizarscan.scanner.base import (PAPEIS_MM, Capacidades, Dispositivo,
                                          ErroScanner, EstadoScanner, Opcoes)

log = log_interno.obter(__name__)

PREFIXO = "escl:"
NS = {"scan": "http://schemas.hp.com/imaging/escl/2011/05/03",
      "pwg": "http://www.pwg.org/schemas/2010/12/sm"}
DPIS_PADRAO = (150, 200, 300, 600)

#: Tempo para achar um scanner na lista (por endereco, em paralelo).
TEMPO_SONDA_S = 3.0
#: Uma pagina no alimentador a 600 dpi pode levar bem mais que isto; o limite e' por pagina.
TEMPO_PAGINA_S = 180.0
ESPERA_S = 1.0
ESPERAS_MAXIMAS = 60


@dataclass
class Fonte:
    largura_max: int = 2550        # 1/300 pol (8,5 pol)
    altura_max: int = 3507         # 1/300 pol (11,69 pol)
    dpis: tuple[int, ...] = DPIS_PADRAO
    #: Todas as resolucoes que a fonte aceita (inclui 75/100, usadas na previa).
    todas: tuple[int, ...] = ()


@dataclass
class Capacidade:
    versao: str = "2.0"
    modelo: str = ""
    uuid: str = ""
    serie: str = ""
    fontes: dict[str, Fonte] = field(default_factory=dict)     # vidro / alimentador / duplex


def _texto(no, caminho: str) -> str:
    achado = no.find(caminho, NS) if no is not None else None
    return (achado.text or "").strip() if achado is not None and achado.text else ""


def _fonte(no) -> Fonte | None:
    if no is None:
        return None
    fonte = Fonte()
    try:
        fonte.largura_max = int(_texto(no, "scan:MaxWidth") or fonte.largura_max)
        fonte.altura_max = int(_texto(no, "scan:MaxHeight") or fonte.altura_max)
    except ValueError:
        pass
    resolucoes: set[int] = set()
    faixa: tuple[int, int] | None = None
    for r in no.iter(f"{{{NS['scan']}}}XResolution"):
        try:
            resolucoes.add(int((r.text or "").strip()))
        except ValueError:
            pass
    faixa_no = no.find(".//scan:XResolutionRange", NS)
    if faixa_no is not None:
        try:
            faixa = (int(_texto(faixa_no, "scan:Min")), int(_texto(faixa_no, "scan:Max")))
        except ValueError:
            faixa = None
    dpis = tuple(d for d in DPIS_PADRAO
                 if d in resolucoes or (faixa is not None and faixa[0] <= d <= faixa[1]))
    fonte.dpis = dpis or DPIS_PADRAO
    candidatas = set(resolucoes)
    if faixa is not None:
        candidatas |= {d for d in (75, 100, *DPIS_PADRAO) if faixa[0] <= d <= faixa[1]}
    fonte.todas = tuple(sorted(candidatas))
    return fonte


def ler_capacidades(xml: bytes) -> Capacidade:
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ErroScanner(t("erro.escl_invalida", detalhe=exc)) from exc
    cap = Capacidade(versao=_texto(raiz, "pwg:Version") or "2.0",
                     modelo=_texto(raiz, "pwg:MakeAndModel"),
                     uuid=_texto(raiz, "scan:UUID"),
                     serie=_texto(raiz, "pwg:SerialNumber"))
    vidro = _fonte(raiz.find("scan:Platen/scan:PlatenInputCaps", NS))
    simples = _fonte(raiz.find("scan:Adf/scan:AdfSimplexInputCaps", NS))
    duplo = _fonte(raiz.find("scan:Adf/scan:AdfDuplexInputCaps", NS))
    opcoes_adf = [(o.text or "").strip() for o in raiz.findall("scan:Adf/scan:AdfOptions/scan:AdfOption", NS)]
    if vidro:
        cap.fontes["vidro"] = vidro
    if simples:
        cap.fontes["alimentador"] = simples
    if duplo or (simples and "Duplex" in opcoes_adf):
        cap.fontes["duplex"] = duplo or simples
    return cap


@dataclass(frozen=True)
class Pedido:
    largura: int        # 1/300 pol
    altura: int         # 1/300 pol
    dpi: int            # o que a fonte aceita, nao necessariamente o escolhido na tela
    x: int = 0          # deslocamento da area, 1/300 pol
    y: int = 0

    @property
    def largura_px(self) -> int:
        return round(self.largura * self.dpi / 300)


def montar_pedido(opcoes: Opcoes, cap: Capacidade) -> Pedido:
    fonte = cap.fontes.get(opcoes.origem) or next(iter(cap.fontes.values()), Fonte())
    medida = PAPEIS_MM.get(opcoes.papel)
    if medida is None:
        largura, altura = fonte.largura_max, fonte.altura_max
    else:
        largura = min(round(medida[0] / 25.4 * 300), fonte.largura_max)
        altura = min(round(medida[1] / 25.4 * 300), fonte.altura_max)
    x = y = 0
    if opcoes.regiao_mm and opcoes.origem == "vidro":
        rx, ry, rl, ra = (round(v / 25.4 * 300) for v in opcoes.regiao_mm)
        x = max(0, min(rx, fonte.largura_max - 8))
        y = max(0, min(ry, fonte.altura_max - 8))
        largura = max(8, min(rl, fonte.largura_max - x))
        altura = max(8, min(ra, fonte.altura_max - y))
    # O alimentador da HP 7740 vai so' ate' 300 dpi (o vidro, ate' 1200): usa o maior que a fonte
    # aceita sem passar do escolhido. A pagina guarda o dpi real, para o PDF sair no tamanho certo.
    aceitos = sorted(fonte.todas or fonte.dpis) or [opcoes.dpi]
    dpi = max((d for d in aceitos if d <= opcoes.dpi), default=aceitos[0])
    return Pedido(largura, altura, dpi, x, y)


def xml_do_trabalho(opcoes: Opcoes, cap: Capacidade, intencao: str = "Document") -> bytes:
    pedido = montar_pedido(opcoes, cap)
    origem = "Platen" if opcoes.origem == "vidro" else "Feeder"
    # Preto e branco e' pedido em cinza e binarizado aqui: nem todo scanner manda 1 bit em JPEG.
    cor = "RGB24" if opcoes.cor == "cor" else "Grayscale8"
    duplex = "true" if opcoes.origem == "duplex" else "false"
    # Ordem dos elementos como no esquema do eSCL: firmware estrito ignora o que vem fora de ordem
    # (e cai no formato padrao, que na HP e' application/octet-stream, imagem crua).
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScanSettings xmlns:scan="{NS['scan']}" xmlns:pwg="{NS['pwg']}">
  <pwg:Version>{cap.versao}</pwg:Version>
  <scan:Intent>{intencao}</scan:Intent>
  <pwg:ScanRegions pwg:MustHonor="false">
    <pwg:ScanRegion>
      <pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>
      <pwg:XOffset>{pedido.x}</pwg:XOffset>
      <pwg:YOffset>{pedido.y}</pwg:YOffset>
      <pwg:Width>{pedido.largura}</pwg:Width>
      <pwg:Height>{pedido.altura}</pwg:Height>
    </pwg:ScanRegion>
  </pwg:ScanRegions>
  <pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>
  <pwg:InputSource>{origem}</pwg:InputSource>
  <scan:XResolution>{pedido.dpi}</scan:XResolution>
  <scan:YResolution>{pedido.dpi}</scan:YResolution>
  <scan:ColorMode>{cor}</scan:ColorMode>
  <scan:Duplex>{duplex}</scan:Duplex>
  <scan:DocumentFormatExt>image/jpeg</scan:DocumentFormatExt>
</scan:ScanSettings>
""".encode("utf-8")


_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def corrigir_altura_jpeg(dados: bytes, altura_padrao: int) -> bytes | None:
    """JPEG com altura 0 no SOF e a altura de verdade num marcador DNL no fim -> JPEG normal.

    E' o que o alimentador da HP manda: ele nao sabe o comprimento da folha quando comeca a
    enviar, entao grava altura 0 e informa as linhas no DNL (FF DC) depois dos dados. O Pillow (e a
    libjpeg) nao aceitam isso ("cannot identify image file"). Devolve None se o JPEG nao e' desse tipo.
    Sem DNL, usa `altura_padrao` (a altura pedida) e a leitura tolera a falta de linhas.
    """
    if not dados.startswith(b"\xff\xd8"):
        return None
    i, sof = 2, None
    while i + 4 <= len(dados):
        if dados[i] != 0xFF:
            return None
        marcador = dados[i + 1]
        if marcador == 0xFF:                    # bytes de preenchimento
            i += 1
            continue
        if marcador == 0x01 or 0xD0 <= marcador <= 0xD8:
            i += 2
            continue
        tamanho = int.from_bytes(dados[i + 2:i + 4], "big")
        if marcador in _SOF:
            sof = i
        if marcador == 0xDA:                    # inicio dos dados comprimidos
            break
        i += 2 + tamanho
    if sof is None or int.from_bytes(dados[sof + 5:sof + 7], "big") != 0:
        return None
    # Nos dados comprimidos todo FF vem seguido de 00 (ou de RST): FF DC so' pode ser o marcador.
    dnl = dados.find(b"\xff\xdc\x00\x04", i)
    altura = altura_padrao
    if dnl >= 0:
        altura = int.from_bytes(dados[dnl + 4:dnl + 6], "big") or altura_padrao
        dados = dados[:dnl] + dados[dnl + 6:]
    if altura <= 0:
        return None
    return dados[:sof + 5] + altura.to_bytes(2, "big") + dados[sof + 7:]


def _abrir(dados: bytes, tolerante: bool = False) -> Image.Image:
    anterior = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = tolerante or anterior
    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
        return imagem
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = anterior


class PaginaVazia(Exception):
    """200 sem corpo: a pagina ainda nao esta' pronta."""


def decodificar(corpo: bytes, tipo: str, pedido: Pedido, modo: str) -> Image.Image:
    """Imagem a partir do que o scanner mandou, mesmo quando nao veio o JPEG pedido.

    Ordem: o que o Pillow reconhece; um JPEG dentro de outra coisa (PDF com DCTDecode, multipart);
    imagem crua (application/octet-stream) com a largura que pedimos.
    """
    if not corpo:
        raise PaginaVazia()
    try:
        imagem = Image.open(io.BytesIO(corpo))
        imagem.load()
        return imagem
    except Exception:                   # noqa: BLE001
        pass
    inicio = corpo.find(b"\xff\xd8\xff")
    fim = corpo.rfind(b"\xff\xd9")
    if 0 <= inicio < fim:
        jpeg = corpo[inicio:fim + 2]
        try:
            return _abrir(jpeg)
        except Exception:               # noqa: BLE001
            pass
        altura_px = round(pedido.altura * pedido.dpi / 300)
        corrigido = corrigir_altura_jpeg(jpeg, altura_px)
        if corrigido is not None:
            try:
                log.info("JPEG com altura 0 (DNL) corrigido")
                return _abrir(corrigido, tolerante=True)
            except Exception as exc:    # noqa: BLE001
                log.info("JPEG com DNL nao abriu mesmo corrigido: %s", exc)
    bytes_por_pixel = 3 if modo == "RGB" else 1
    for largura in dict.fromkeys((pedido.largura_px, round(pedido.largura * pedido.dpi / 300) + 1)):
        linha = largura * bytes_por_pixel
        if largura > 0 and len(corpo) % linha == 0 and len(corpo) // linha > 16:
            return Image.frombytes(modo, (largura, len(corpo) // linha), corpo)
    _guardar_amostra(corpo)
    raise ErroScanner(t("erro.escl_formato", tipo=tipo or t("erro.sem_tipo"), bytes=len(corpo),
                        inicio=corpo[:8].hex()))


def _guardar_amostra(corpo: bytes) -> None:
    try:
        pasta = log_interno.pasta_de_dados()
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "ultima_pagina_recebida.bin").write_bytes(corpo[:64 * 1024 * 1024])
    except OSError:
        pass


def _abridor(verificar: bool) -> urllib.request.OpenerDirector:
    contexto = ssl.create_default_context()
    if not verificar:
        # So' para impressora da rede local (ver `eh_rede_local`): o certificado delas e' autoassinado.
        contexto.check_hostname = False  # nosemgrep
        contexto.verify_mode = ssl.CERT_NONE  # nosemgrep
    # ProxyHandler({}): proxy do sistema nunca ve' trafego para a impressora da rede local.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPSHandler(context=contexto))


_ABRIDOR = _abridor(verificar=True)
_ABRIDOR_LOCAL = _abridor(verificar=False)


def eh_rede_local(host: str) -> bool:
    """True para IP privado, de enlace local ou loopback, e para nomes `.local` ou de uma so' palavra.

    So' nesses casos o certificado HTTPS autoassinado da impressora e' aceito sem conferencia; para
    qualquer endereco da internet o certificado precisa ser valido.
    """
    host = (host or "").strip("[]").lower()
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_link_local or ip.is_loopback
    except ValueError:
        return host.endswith(".local") or ("." not in host and host != "")


def pedir(metodo: str, url: str, corpo: bytes | None = None,
          tempo: float = 15.0) -> tuple[int, dict, bytes]:
    """(status, cabecalhos, corpo). Erro de rede vira ErroScanner; status HTTP de erro, nao."""
    cabecalhos = {"Content-Type": "text/xml"} if corpo is not None else {}
    pedido = urllib.request.Request(url, data=corpo, method=metodo, headers=cabecalhos)
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        try:
            with _ABRIDOR.open(pedido, timeout=tempo) as resposta:
                return resposta.status, dict(resposta.headers), resposta.read()
        except urllib.error.URLError as exc:
            if not (isinstance(exc.reason, ssl.SSLCertVerificationError) and eh_rede_local(host)):
                raise
            # Certificado autoassinado de impressora na rede local: aceita, cifrado mas sem conferencia.
            with _ABRIDOR_LOCAL.open(pedido, timeout=tempo) as resposta:
                return resposta.status, dict(resposta.headers), resposta.read()
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, dict(exc.headers or {}), exc.read() or b""
        finally:
            exc.close()
    except (urllib.error.URLError, OSError) as exc:
        raise ErroScanner(t("erro.rede", url=url, motivo=getattr(exc, "reason", exc))) from exc


def bases_para(endereco: str) -> list[str]:
    """Endereco digitado (IP, nome ou URL) -> URLs base do eSCL a tentar, na ordem."""
    endereco = endereco.strip().rstrip("/")
    if not endereco:
        return []
    if "://" in endereco:
        partes = urllib.parse.urlsplit(endereco)
        caminho = partes.path if partes.path and partes.path != "/" else "/eSCL"
        return [f"{partes.scheme}://{partes.netloc}{caminho}"]
    return [f"http://{endereco}/eSCL", f"https://{endereco}/eSCL"]


def _dormir(segundos: float, cancelado: Callable[[], bool]) -> None:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim and not cancelado():
        time.sleep(min(0.2, max(0.0, fim - time.monotonic())))


class ScannerEscl:
    def __init__(self, enderecos: Callable[[], Iterable[str]] = lambda: (),
                 descobrir: Callable[[], Iterable[str]] | None = None):
        """`enderecos`: os digitados pelo usuario. `descobrir`: os achados na rede (mDNS, portas)."""
        self._enderecos = enderecos
        self._descobrir = descobrir
        self._caps: dict[str, Capacidade] = {}
        self.dicas: list[str] = []          # nomes vindos do WIA (ex.: SCANNER01), preenchidos por fora

    def preparar_thread(self) -> None:
        pass

    def encerrar_thread(self) -> None:
        pass

    # -- descoberta -----------------------------------------------------------
    def _sondar(self, base: str) -> tuple[str, Capacidade] | None:
        try:
            status, _, corpo = pedir("GET", f"{base}/ScannerCapabilities", tempo=TEMPO_SONDA_S)
        except ErroScanner:
            return None
        if status != 200:
            return None
        try:
            return base, ler_capacidades(corpo)
        except ErroScanner:
            return None

    def candidatos(self) -> list[str]:
        vistos: list[str] = []
        fontes = [list(self._enderecos())]
        if self._descobrir is not None:
            try:
                fontes.append(list(self._descobrir()))
            except Exception as exc:        # noqa: BLE001 - descoberta e' best-effort
                log.info("descoberta falhou: %s", exc)
        for dica in self.dicas:
            fontes.append([f"{dica}.local", dica])
        for lista in fontes:
            for endereco in lista:
                for base in bases_para(endereco):
                    if base not in vistos:
                        vistos.append(base)
        return vistos

    def listar(self) -> list[Dispositivo]:
        bases = self.candidatos()
        if not bases:
            return []
        with ThreadPoolExecutor(max_workers=min(16, len(bases))) as grupo:
            resultados = list(grupo.map(self._sondar, bases))
        achados: list[Dispositivo] = []
        chaves: set[str] = set()
        for resultado in resultados:            # na ordem dos candidatos: digitado vence
            if resultado is None:
                continue
            base, cap = resultado
            chave = cap.uuid or cap.serie or base
            if chave in chaves:
                continue
            chaves.add(chave)
            self._caps[base] = cap
            host = urllib.parse.urlsplit(base).hostname or base
            nome = t("rede.nome", modelo=cap.modelo or t("rede.modelo_padrao"), host=host)
            achados.append(Dispositivo(PREFIXO + base, nome))
        log.info("eSCL: %s candidato(s), %s scanner(s)", len(bases), len(achados))
        return achados

    def _capacidade(self, base: str) -> Capacidade:
        if base not in self._caps:
            status, _, corpo = pedir("GET", f"{base}/ScannerCapabilities")
            if status != 200:
                raise ErroScanner(t("erro.escl_capacidades", status=status))
            self._caps[base] = ler_capacidades(corpo)
        return self._caps[base]

    def capacidades(self, dispositivo_id: str) -> Capacidades:
        cap = self._capacidade(dispositivo_id.removeprefix(PREFIXO))
        origens = tuple(o for o in ("vidro", "alimentador", "duplex") if o in cap.fontes) or ("vidro",)
        dpis = sorted({d for f in cap.fontes.values() for d in f.dpis}) or list(DPIS_PADRAO)
        vidro = cap.fontes.get("vidro")
        vidro_mm = (vidro.largura_max / 300 * 25.4, vidro.altura_max / 300 * 25.4) if vidro else None
        return Capacidades(origens=origens, dpis=tuple(dpis), vidro_mm=vidro_mm)

    def estado(self, dispositivo_id: str) -> EstadoScanner:
        """Papel no alimentador, pelo AdfState do ScannerStatus (None se o scanner nao informa)."""
        _, adf = self._estado(dispositivo_id.removeprefix(PREFIXO))
        return EstadoScanner(papel={"ScannerAdfLoaded": True, "ScannerAdfEmpty": False}.get(adf))

    def previa(self, dispositivo_id: str) -> Image.Image:
        """Vidro inteiro em baixa resolucao (75 dpi), para escolher a area a digitalizar."""
        opcoes = Opcoes(origem="vidro", cor="cor", dpi=75, papel="total")
        imagens = list(self.digitalizar(dispositivo_id, opcoes, lambda: False, intencao="Preview"))
        if not imagens:
            raise ErroScanner(t("erro.nenhuma_pagina"))
        return imagens[0]

    def diagnostico(self, dispositivo_id: str) -> str:
        base = dispositivo_id.removeprefix(PREFIXO)
        linhas = [f"DigitalizarScan - diagnostico eSCL\nBase: {base}"]
        for recurso in ("ScannerCapabilities", "ScannerStatus"):
            try:
                status, _, corpo = pedir("GET", f"{base}/{recurso}")
                linhas.append(f"\n[{recurso}] HTTP {status}\n{corpo.decode('utf-8', 'replace')}")
            except ErroScanner as exc:
                linhas.append(f"\n[{recurso}] {exc}")
        linhas.append("\n[ultimas linhas do log]")
        try:
            arquivo = log_interno.pasta_de_dados() / "digitalizarscan.log"
            linhas.extend(arquivo.read_text(encoding="utf-8", errors="replace").splitlines()[-60:])
        except OSError:
            linhas.append("(sem log)")
        return "\n".join(linhas) + "\n"

    # -- digitalizacao --------------------------------------------------------
    def _estado(self, base: str) -> tuple[str, str]:
        status, _, corpo = pedir("GET", f"{base}/ScannerStatus")
        if status != 200:
            return "", ""
        try:
            raiz = ET.fromstring(corpo)
        except ET.ParseError:
            return "", ""
        return _texto(raiz, "pwg:State"), _texto(raiz, "scan:AdfState")

    def _criar_trabalho(self, base: str, xml: bytes, cancelado: Callable[[], bool]) -> str:
        for _ in range(ESPERAS_MAXIMAS):
            status, cabecalhos, corpo = pedir("POST", f"{base}/ScanJobs", xml)
            if status in (200, 201):
                local = next((v for k, v in cabecalhos.items() if k.lower() == "location"), "")
                if not local:
                    raise ErroScanner(t("erro.escl_sem_local"))
                return urllib.parse.urljoin(base + "/", local).rstrip("/")
            if status == 503 and not cancelado():
                _dormir(ESPERA_S * 2, cancelado)
                continue
            if status == 409:
                raise ErroScanner(t("erro.escl_recusou_409"))
            raise ErroScanner(t("erro.escl_recusou", status=status,
                                detalhe=corpo[:200].decode("utf-8", "replace")).strip())
        raise ErroScanner(t("erro.ocupado"))

    def digitalizar(self, dispositivo_id: str, opcoes: Opcoes,
                    cancelado: Callable[[], bool], intencao: str = "Document") -> Iterator[Image.Image]:
        base = dispositivo_id.removeprefix(PREFIXO)
        cap = self._capacidade(base)
        _, adf = self._estado(base)
        if opcoes.origem != "vidro" and adf == "ScannerAdfEmpty":
            raise ErroScanner(t("erro.sem_papel"))

        pedido = montar_pedido(opcoes, cap)
        modo = "RGB" if opcoes.cor == "cor" else "L"
        trabalho = self._criar_trabalho(base, xml_do_trabalho(opcoes, cap, intencao), cancelado)
        log.info("eSCL: trabalho %s", trabalho)
        entregues = esperas = 0
        terminou = False
        try:
            while not cancelado():
                status, cabecalhos, corpo = pedir("GET", f"{trabalho}/NextDocument", tempo=TEMPO_PAGINA_S)
                if status == 200:
                    tipo = next((v for k, v in cabecalhos.items() if k.lower() == "content-type"), "")
                    log.info("eSCL: pagina %s: %s, %s bytes", entregues + 1, tipo, len(corpo))
                    try:
                        imagem = decodificar(corpo, tipo, pedido, modo)
                    except PaginaVazia:
                        if esperas >= ESPERAS_MAXIMAS:
                            raise ErroScanner(t("erro.pagina_vazia")) from None
                        esperas += 1
                        _dormir(ESPERA_S, cancelado)
                        continue
                    esperas = 0
                    if opcoes.cor == "pb":
                        imagem = imagem.convert("L").point(lambda v: 255 if v > 128 else 0).convert("1")
                    imagem.info["dscan_dpi"] = pedido.dpi
                    entregues += 1
                    yield imagem
                    if opcoes.origem == "vidro":
                        terminou = True
                        return
                    continue
                if status == 404:
                    terminou = True
                    if entregues == 0:
                        raise ErroScanner(t("erro.nenhuma_pagina"))
                    return
                if status == 503 and esperas < ESPERAS_MAXIMAS:
                    esperas += 1
                    _dormir(ESPERA_S, cancelado)
                    continue
                raise ErroScanner(t("erro.interrompido", status=status))
        finally:
            if not terminou:
                try:
                    pedir("DELETE", trabalho, tempo=5)
                except ErroScanner:
                    pass
