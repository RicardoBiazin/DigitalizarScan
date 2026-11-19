# DigitalizarScan

**Português** · [English](README.en.md) · [Español](README.es.md) · [中文](README.zh-CN.md)

Programa de desktop para Windows que digitaliza documentos direto da impressora multifuncional,
junta as páginas, reconhece o texto (OCR) e salva em PDF pesquisável, JPG ou PNG.
Licença [MIT](LICENSE).

## O que faz

- **Digitaliza pela rede** (eSCL/AirScan, o protocolo da maioria das multifuncionais HP, Canon, Epson e
  Brother recentes) **ou pelo WIA** do Windows (scanners USB e drivers do fabricante).
- **Todas as folhas do alimentador automático**, frente e verso e vidro. Cor, tons de cinza ou preto e
  branco; 75 a 1200 dpi conforme o equipamento; A4, Carta, Ofício ou área total.
- **Prévia do vidro** com seleção de uma área para digitalizar só um pedaço.
- **Indicador de papel no alimentador**: mostra se há papel e escolhe Alimentador ou Vidro sozinho.
- **Organiza as páginas**: girar, mover, excluir, arrastar para reordenar, abrir uma página.
- **Salva** em PDF (um arquivo), JPG ou PNG, sem nunca sobrescrever um arquivo pela metade.
- **OCR** com o Tesseract embutido (português, inglês, espanhol e chinês simplificado): o PDF sai com
  texto selecionável e pesquisável.
- **Interface em 4 idiomas** (português, English, Español, 中文) e **tema** claro, escuro ou do sistema.

## Como usar

1. Ligue a multifuncional e abra o `DigitalizarScan.exe`.
2. Escolha o scanner. Os de rede aparecem como “… — rede (IP)”; os do WIA, como “… — WIA”. Se a sua
   impressora não aparecer sozinha, use **Adicionar pelo endereço…** e digite o IP dela.
3. Escolha a origem, a cor, a resolução e o papel. Clique em **Digitalizar**. Para juntar mais páginas,
   clique de novo.
4. No vidro, **Prévia…** mostra o vidro inteiro: arraste um retângulo e use **Usar esta área**.
5. Ajuste as páginas, escolha o formato, marque **Reconhecer texto (OCR)** se quiser e clique em **Salvar…**.

Menu **Exibir**: tema (sistema, claro, escuro) e idioma. Menu **Ajuda > Diagnóstico do scanner** grava um
`diagnostico.txt` com o que o equipamento informa, útil para relatar um problema.

Sem scanner à mão, `DigitalizarScan.exe --demo` usa um scanner de demonstração.

## Requisitos

- Windows 10 ou 11 (64 bits).
- Multifuncional de rede com eSCL/AirScan (recomendado: entrega todas as folhas do alimentador) ou
  qualquer scanner que apareça em *Dispositivos de imagem* (WIA). Com impressora de rede instalada por
  WSD, o WIA entrega só a primeira folha do alimentador; por isso o eSCL vem primeiro na lista.
- O OCR usa o Tesseract que vai dentro do pacote. Sem ele o PDF sai sem texto e o programa avisa.

Baixe o ZIP da [última versão](../../releases/latest), extraia a pasta inteira e abra `DigitalizarScan.exe`.

## Desenvolvimento

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File ferramentas\baixar_tesseract.ps1   # OCR (opcional)
.venv\Scripts\python.exe app.py --demo
.venv\Scripts\python.exe tests\rodar_todos.py
build.bat
```

`build.bat` roda a suíte de testes, empacota com o PyInstaller (pasta única), confere o executável
(`--autoverificacao`), abre a janela de verdade (fumaça) e gera o ZIP em `dist\`. Os testes não precisam
de impressora: usam um scanner de mentira, um COM do WIA simulado e um servidor eSCL local.

| Parte | Arquivo |
|---|---|
| Scanner de rede eSCL (HTTP) | `digitalizarscan/scanner/escl.py` |
| Descoberta (mDNS, portas do Windows) | `digitalizarscan/scanner/descoberta.py` |
| eSCL + WIA numa lista | `digitalizarscan/scanner/composto.py` |
| Scanner WIA (COM) | `digitalizarscan/scanner/wia.py` |
| Scanner de mentira (testes, `--demo`) | `digitalizarscan/scanner/falso.py` |
| Páginas em disco (girar, ordem) | `digitalizarscan/documento.py` |
| PDF, JPG/PNG, gravação atômica | `digitalizarscan/saida/` |
| OCR (Tesseract como processo) | `digitalizarscan/saida/ocr.py` |
| Janela e prévia | `digitalizarscan/interface/` |
| Idiomas (catálogos) e tema | `digitalizarscan/i18n.py`, `digitalizarscan/idiomas/`, `digitalizarscan/tema.py` |

Preferências em `%APPDATA%\DigitalizarScan\configuracao.json`; log em `digitalizarscan.log` na mesma pasta.
Para acrescentar um idioma: copie `digitalizarscan/idiomas/en.py`, traduza e registre o código em
`digitalizarscan/i18n.py`; `tests/teste_idiomas.py` confere que não falta nenhuma chave.

## Limites conhecidos

- A interface e este README em inglês, espanhol e chinês foram traduzidos sem revisão de falante nativo;
  correções são bem-vindas.
- Frente e verso pelo WIA depende de o driver oferecer o modo; pelo eSCL depende da impressora.
- Testado no equipamento real com uma HP OfficeJet Pro 7740 (eSCL). Outros modelos seguem o mesmo padrão,
  mas podem ter particularidades; o diagnóstico ajuda a tratá-las.

## Licença

[MIT](LICENSE). Componentes de terceiros (Qt for Python, pywin32, Pillow, Tesseract) em
[AVISOS_DE_TERCEIROS.md](AVISOS_DE_TERCEIROS.md).
