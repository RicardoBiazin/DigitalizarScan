"""Servidor eSCL de mentira (HTTP local) para testar ScannerEscl sem impressora."""

from __future__ import annotations

import io
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

CAPACIDADES = """<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerCapabilities xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
                          xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
  <pwg:Version>2.63</pwg:Version>
  <pwg:MakeAndModel>HP OfficeJet Pro 7740 series</pwg:MakeAndModel>
  <pwg:SerialNumber>SN0000000A</pwg:SerialNumber>
  <scan:UUID>{uuid}</scan:UUID>
  <scan:Platen><scan:PlatenInputCaps>
    <scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>3508</scan:MaxHeight>
    <scan:SettingProfiles><scan:SettingProfile>
      <scan:ColorModes><scan:ColorMode>RGB24</scan:ColorMode><scan:ColorMode>Grayscale8</scan:ColorMode></scan:ColorModes>
      <scan:SupportedResolutions><scan:DiscreteResolutions>
        <scan:DiscreteResolution><scan:XResolution>75</scan:XResolution><scan:YResolution>75</scan:YResolution></scan:DiscreteResolution>
        <scan:DiscreteResolution><scan:XResolution>200</scan:XResolution><scan:YResolution>200</scan:YResolution></scan:DiscreteResolution>
        <scan:DiscreteResolution><scan:XResolution>300</scan:XResolution><scan:YResolution>300</scan:YResolution></scan:DiscreteResolution>
        <scan:DiscreteResolution><scan:XResolution>600</scan:XResolution><scan:YResolution>600</scan:YResolution></scan:DiscreteResolution>
      </scan:DiscreteResolutions></scan:SupportedResolutions>
    </scan:SettingProfile></scan:SettingProfiles>
  </scan:PlatenInputCaps></scan:Platen>
  <scan:Adf>
    <scan:AdfSimplexInputCaps>
      <scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>4200</scan:MaxHeight>
      <scan:SettingProfiles><scan:SettingProfile><scan:SupportedResolutions><scan:XResolutionRange>
        <scan:Min>100</scan:Min><scan:Max>300</scan:Max><scan:Step>1</scan:Step>
      </scan:XResolutionRange></scan:SupportedResolutions></scan:SettingProfile></scan:SettingProfiles>
    </scan:AdfSimplexInputCaps>
    {duplex}
  </scan:Adf>
</scan:ScannerCapabilities>"""

DUPLEX = """<scan:AdfDuplexInputCaps><scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>4200</scan:MaxHeight>
</scan:AdfDuplexInputCaps>"""


def jpeg(numero: int) -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", (100 + numero, 140), (200, 200, 200)).save(saida, "JPEG")
    return saida.getvalue()


def jpeg_dnl(largura: int, altura: int, com_dnl: bool = True) -> bytes:
    """Como o alimentador da HP manda: altura 0 no SOF e as linhas num DNL depois dos dados."""
    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), (120, 30, 200)).save(saida, "JPEG")
    dados = saida.getvalue()
    sof = dados.find(b"\xff\xc0")
    dados = dados[:sof + 5] + b"\x00\x00" + dados[sof + 7:]
    if com_dnl:
        dados = dados[:-2] + b"\xff\xdc\x00\x04" + altura.to_bytes(2, "big") + b"\xff\xd9"
    return dados


class Impressora:
    """Estado do servidor; os testes mexem nisto direto."""

    def __init__(self, folhas=8, duplex=True, ocupado_ao_criar=0, esperas_por_pagina=0,
                 location_relativo=True, adf_vazio=False, formato="jpeg"):
        self.folhas = folhas
        self.duplex = duplex
        self.ocupado_ao_criar = ocupado_ao_criar
        self.esperas_por_pagina = esperas_por_pagina
        self.location_relativo = location_relativo
        self.adf_vazio = adf_vazio
        self.formato = formato          # jpeg | cru | pdf | vazio_antes | lixo
        self.vazios = 0
        self.uuid = str(uuid.uuid4())
        self.trabalhos: dict[str, dict] = {}
        self.pedidos: list[tuple[str, str, bytes]] = []
        self.apagados: list[str] = []


def iniciar(impressora: Impressora) -> tuple[ThreadingHTTPServer, str]:
    class Tratador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _responder(self, codigo, corpo=b"", tipo="text/xml", extra=None):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            impressora.pedidos.append(("GET", self.path, b""))
            if self.path == "/eSCL/ScannerCapabilities":
                xml = CAPACIDADES.format(uuid=impressora.uuid, duplex=DUPLEX if impressora.duplex else "")
                return self._responder(200, xml.encode())
            if self.path == "/eSCL/ScannerStatus":
                adf = "ScannerAdfEmpty" if impressora.adf_vazio else "ScannerAdfLoaded"
                xml = (f'<scan:ScannerStatus xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03" '
                       f'xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm"><pwg:State>Idle</pwg:State>'
                       f'<scan:AdfState>{adf}</scan:AdfState></scan:ScannerStatus>')
                return self._responder(200, xml.encode())
            if self.path.endswith("/NextDocument"):
                ident = self.path.split("/")[-2]
                trabalho = impressora.trabalhos.get(ident)
                if trabalho is None:
                    return self._responder(404)
                if trabalho["esperas"] > 0:
                    trabalho["esperas"] -= 1
                    return self._responder(503)
                if trabalho["restantes"] <= 0:
                    return self._responder(404)
                if impressora.formato == "vazio_antes" and impressora.vazios < 2:
                    impressora.vazios += 1
                    return self._responder(200, b"", "image/jpeg")
                trabalho["restantes"] -= 1
                trabalho["entregues"] += 1
                trabalho["esperas"] = impressora.esperas_por_pagina
                n = trabalho["entregues"]
                if impressora.formato == "cru":
                    # RGB cru na largura pedida (A4 a 300 dpi = 2480 px), 20 linhas
                    return self._responder(200, bytes([90, 120, 150]) * 2480 * 20, "application/octet-stream")
                if impressora.formato == "pdf":
                    corpo = (b"%PDF-1.4\n1 0 obj<</Filter/DCTDecode>>stream\n" + jpeg(n)
                             + b"\nendstream\n%%EOF")
                    return self._responder(200, corpo, "application/pdf")
                if impressora.formato == "dnl":
                    return self._responder(200, jpeg_dnl(2480, 3000 + n), "image/jpeg")
                if impressora.formato == "dnl_sem":
                    return self._responder(200, jpeg_dnl(2480, 3508, com_dnl=False), "image/jpeg")
                if impressora.formato == "lixo":
                    return self._responder(200, b"nada que preste" * 7, "application/octet-stream")
                return self._responder(200, jpeg(n), "image/jpeg")
            return self._responder(404)

        def do_POST(self):
            corpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            impressora.pedidos.append(("POST", self.path, corpo))
            if self.path != "/eSCL/ScanJobs":
                return self._responder(404)
            if impressora.ocupado_ao_criar > 0:
                impressora.ocupado_ao_criar -= 1
                return self._responder(503)
            if b"<pwg:InputSource>Platen" in corpo:
                restantes = 1
            else:
                if impressora.adf_vazio:
                    return self._responder(409)
                restantes = impressora.folhas * (2 if b"<scan:Duplex>true" in corpo else 1)
            ident = uuid.uuid4().hex
            impressora.trabalhos[ident] = {"restantes": restantes, "entregues": 0,
                                           "esperas": impressora.esperas_por_pagina}
            local = f"/eSCL/ScanJobs/{ident}"
            if not impressora.location_relativo:
                local = f"http://127.0.0.1:{self.server.server_address[1]}{local}"
            return self._responder(201, extra={"Location": local})

        def do_DELETE(self):
            impressora.pedidos.append(("DELETE", self.path, b""))
            impressora.apagados.append(self.path)
            return self._responder(200)

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Tratador)
    servidor.handle_error = lambda *a: None     # sonda https num servidor http: ruido esperado
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"127.0.0.1:{servidor.server_address[1]}"
