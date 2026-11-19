"""Onde procurar scanners eSCL na rede, sem biblioteca externa.

1. mDNS (Bonjour): pergunta por _uscan._tcp e _uscans._tcp em 224.0.0.251:5353. A pergunta sai
   de uma porta qualquer (nao da 5353, que o Windows ja' usa), entao as respostas vem por unicast
   para nos ("legacy unicast", RFC 6762 secao 6.7).
2. Portas TCP/IP de impressora do Windows (registro): a multifuncional costuma estar instalada
   como impressora, e o IP dela esta' la'.

Tudo aqui e' melhor esforco: falhar devolve lista vazia, nunca excecao.
"""

from __future__ import annotations

import secrets
import socket
import struct
import time
from dataclasses import dataclass

from digitalizarscan import log_interno

log = log_interno.obter(__name__)

GRUPO_MDNS = ("224.0.0.251", 5353)
SERVICOS = ("_uscan._tcp.local", "_uscans._tcp.local")
T_A, T_PTR, T_TXT, T_SRV = 1, 12, 16, 33


@dataclass(frozen=True)
class Servico:
    instancia: str
    host: str
    porta: int
    seguro: bool
    caminho: str = "eSCL"

    @property
    def url(self) -> str:
        esquema = "https" if self.seguro else "http"
        padrao = 443 if self.seguro else 80
        porta = "" if self.porta == padrao else f":{self.porta}"
        return f"{esquema}://{self.host}{porta}/{self.caminho.strip('/') or 'eSCL'}"


# -- DNS minimo -------------------------------------------------------------------
def codificar_nome(nome: str) -> bytes:
    saida = b""
    for parte in nome.strip(".").split("."):
        dados = parte.encode("utf-8")
        saida += bytes([len(dados)]) + dados
    return saida + b"\x00"


def pergunta(nomes: tuple[str, ...] = SERVICOS, ident: int = 0) -> bytes:
    cabecalho = struct.pack("!HHHHHH", ident, 0, len(nomes), 0, 0, 0)
    corpo = b"".join(codificar_nome(n) + struct.pack("!HH", T_PTR, 0x8001) for n in nomes)  # QU
    return cabecalho + corpo


def ler_nome(dados: bytes, pos: int) -> tuple[str, int]:
    partes: list[str] = []
    fim = None
    saltos = 0
    while True:
        if pos >= len(dados):
            raise ValueError("nome truncado")
        tamanho = dados[pos]
        if tamanho & 0xC0 == 0xC0:              # ponteiro de compressao
            if pos + 1 >= len(dados):
                raise ValueError("ponteiro truncado")
            if fim is None:
                fim = pos + 2
            pos = ((tamanho & 0x3F) << 8) | dados[pos + 1]
            saltos += 1
            if saltos > 50:
                raise ValueError("laco de ponteiros")
            continue
        if tamanho == 0:
            pos += 1
            break
        partes.append(dados[pos + 1:pos + 1 + tamanho].decode("utf-8", "replace"))
        pos += 1 + tamanho
    return ".".join(partes), (fim if fim is not None else pos)


def ler_registros(dados: bytes) -> list[tuple[str, int, bytes, int]]:
    """(nome, tipo, dados_do_registro, deslocamento_dos_dados) das secoes de resposta."""
    _, _, qd, an, ns, ar = struct.unpack("!HHHHHH", dados[:12])
    pos = 12
    for _ in range(qd):
        _, pos = ler_nome(dados, pos)
        pos += 4
    registros = []
    for _ in range(an + ns + ar):
        nome, pos = ler_nome(dados, pos)
        tipo, _, _, tamanho = struct.unpack("!HHIH", dados[pos:pos + 10])
        pos += 10
        registros.append((nome.lower(), tipo, dados[pos:pos + tamanho], pos))
        pos += tamanho
    return registros


def montar_servicos(pacotes: list[bytes]) -> list[Servico]:
    ptr: list[tuple[str, bool]] = []
    srv: dict[str, tuple[str, int]] = {}
    txt: dict[str, dict[str, str]] = {}
    enderecos: dict[str, str] = {}
    for pacote in pacotes:
        try:
            registros = ler_registros(pacote)
        except (ValueError, struct.error):
            continue
        for nome, tipo, rdata, pos in registros:
            try:
                if tipo == T_PTR and nome in SERVICOS:
                    instancia, _ = ler_nome(pacote, pos)
                    ptr.append((instancia.lower(), nome.startswith("_uscans")))
                elif tipo == T_SRV:
                    _, _, porta = struct.unpack("!HHH", rdata[:6])
                    alvo, _ = ler_nome(pacote, pos + 6)
                    srv[nome] = (alvo.lower(), porta)
                elif tipo == T_TXT:
                    campos, i = {}, 0
                    while i < len(rdata):
                        n = rdata[i]
                        par = rdata[i + 1:i + 1 + n].decode("utf-8", "replace")
                        i += 1 + n
                        chave, _, valor = par.partition("=")
                        campos[chave.lower()] = valor
                    txt[nome] = campos
                elif tipo == T_A and len(rdata) == 4:
                    enderecos[nome] = socket.inet_ntoa(rdata)
            except (ValueError, struct.error, OSError):
                continue
    servicos, vistos = [], set()
    for instancia, seguro in ptr:
        if instancia not in srv:
            continue
        alvo, porta = srv[instancia]
        host = enderecos.get(alvo, alvo)
        caminho = txt.get(instancia, {}).get("rs", "eSCL")
        servico = Servico(instancia, host, porta, seguro, caminho)
        if servico.url not in vistos:
            vistos.add(servico.url)
            servicos.append(servico)
    # http antes de https: e' o que menos falha com certificado de impressora.
    return sorted(servicos, key=lambda s: s.seguro)


def procurar_mdns(tempo: float = 1.5) -> list[Servico]:
    pacotes: list[bytes] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            s.bind(("", 0))
            s.settimeout(0.2)
            s.sendto(pergunta(ident=secrets.randbelow(0xFFFF) + 1), GRUPO_MDNS)
            fim = time.monotonic() + tempo
            while time.monotonic() < fim:
                try:
                    dados, _ = s.recvfrom(9000)
                    pacotes.append(dados)
                except socket.timeout:
                    continue
    except OSError as exc:
        log.info("mDNS indisponivel: %s", exc)
    servicos = montar_servicos(pacotes)
    log.info("mDNS: %s resposta(s), %s servico(s) eSCL", len(pacotes), len(servicos))
    return servicos


def portas_de_impressora() -> list[str]:
    """IPs/nomes das portas 'Standard TCP/IP' das impressoras instaladas no Windows."""
    try:
        import winreg
    except ImportError:
        return []
    chave = r"SYSTEM\CurrentControlSet\Control\Print\Monitors\Standard TCP/IP Port\Ports"
    achados: list[str] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chave) as portas:
            i = 0
            while True:
                try:
                    nome = winreg.EnumKey(portas, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(portas, nome) as porta:
                        for valor in ("HostName", "IPAddress"):
                            try:
                                dado, _ = winreg.QueryValueEx(porta, valor)
                            except OSError:
                                continue
                            if isinstance(dado, str) and dado.strip() and dado.strip() not in achados:
                                achados.append(dado.strip())
                except OSError:
                    continue
    except OSError:
        return []
    return achados


def descobrir() -> list[str]:
    """Enderecos (URLs eSCL ou hosts) para o ScannerEscl sondar."""
    return [s.url for s in procurar_mdns()] + portas_de_impressora()
