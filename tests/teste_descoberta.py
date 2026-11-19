"""mDNS sem rede: monta uma resposta DNS de verdade (com compressao) e confere a leitura."""

import socket
import struct

from ajudantes import encerrar, igual, verificar

from digitalizarscan.scanner import descoberta as d


def registro(nome_bytes: bytes, tipo: int, rdata: bytes) -> bytes:
    return nome_bytes + struct.pack("!HHIH", tipo, 0x8001, 120, len(rdata)) + rdata


# pergunta: dois PTR com o bit QU
p = d.pergunta(ident=7)
igual(struct.unpack("!HHHHHH", p[:12]), (7, 0, 2, 0, 0, 0), "cabecalho da pergunta")
verificar(d.codificar_nome("_uscan._tcp.local") in p and p.count(struct.pack("!HH", 12, 0x8001)) == 2,
          "PTR com bit QU")

# resposta: PTR -> instancia; SRV -> alvo/porta (nome comprimido); TXT rs; A
servico = d.codificar_nome("_uscan._tcp.local")
cab = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 3)
pos_servico = 12
rotulo = "HP OfficeJet Pro 7740 [A1B2C3]".encode()
instancia = bytes([len(rotulo)]) + rotulo + b"\xc0" + bytes([pos_servico])
ptr = registro(servico, 12, instancia)
pacote = cab + ptr
pos_instancia = len(cab) + len(servico) + 10                       # onde a instancia comeca
ponteiro_instancia = b"\xc0" + bytes([pos_instancia])
alvo = d.codificar_nome("SCANNER01.local")
srv = registro(ponteiro_instancia, 33, struct.pack("!HHH", 0, 0, 8080) + alvo)
pacote += srv
pos_alvo = len(pacote) - len(alvo)
txt_dados = b"".join(bytes([len(x)]) + x for x in (b"txtvers=1", b"rs=eSCL", b"ty=HP OfficeJet Pro 7740"))
txt = registro(ponteiro_instancia, 16, txt_dados)
a = registro(b"\xc0" + bytes([pos_alvo]), 1, socket.inet_aton("192.0.2.10"))
pacote += txt + a

servicos = d.montar_servicos([pacote])
igual(len(servicos), 1, "um servico")
s = servicos[0]
igual((s.host, s.porta, s.seguro, s.caminho), ("192.0.2.10", 8080, False, "eSCL"), "host pelo A, porta do SRV")
igual(s.url, "http://192.0.2.10:8080/eSCL", "url")
igual(d.Servico("x", "h", 443, True).url, "https://h/eSCL", "https na porta padrao")

# lixo e pacote truncado nao derrubam
igual(d.montar_servicos([b"", b"\x00" * 5, pacote[:40]]), [], "pacotes quebrados ignorados")
laco = struct.pack("!HHHHHH", 0, 0, 0, 1, 0, 0) + b"\xc0\x0c"
igual(d.montar_servicos([laco]), [], "ponteiro em laco nao trava")

# rede real: so' nao pode explodir
verificar(isinstance(d.procurar_mdns(0.3), list), "procurar_mdns devolve lista")
verificar(isinstance(d.portas_de_impressora(), list), "portas do registro devolve lista")

encerrar()
