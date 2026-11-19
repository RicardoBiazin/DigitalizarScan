# CLAUDE.md: DigitalizarScan

Digitalização pela multifuncional em Python 3.13 + PySide6 6.12.0 (WIA por pywin32 e eSCL por HTTP).
Repositório público, licença MIT. Este arquivo é lido antes de qualquer alteração. As regras abaixo
existem porque a alternativa já causou defeito ou foi decidida de propósito.

## Regras inegociáveis

1. **Nada de execução dinâmica.** Sem `eval`, `exec`, `pickle`, `marshal`, `shell=True`,
   `os.system`. `tests/teste_higiene.py` varre o código e falha se aparecer. O Tesseract roda
   como processo com lista de argumentos.
2. **Nunca perder uma digitalização em silêncio.** Gravação atômica (`saida/atomico.py`):
   arquivo temporário e troca; o original fica intacto se algo falhar. Se o OCR falhar, o PDF
   sai sem texto e o aviso aparece (`exportar.py`).
3. **Texto de tela vem do catálogo** (`digitalizarscan/idiomas/pt|en|es|zh.py`, via `t("chave")`),
   nunca literal no código. `tests/teste_idiomas.py` exige as mesmas chaves e `{marcadores}` nos 4
   idiomas e falha se sobrar texto acentuado fora do catálogo. Comentário, docstring e log podem ser ASCII.
4. **Versão em três lugares, que têm de bater:** `digitalizarscan/__init__.py` (`VERSAO`),
   `versao.txt` e `digitalizarscan.manifest`, mais a entrada no `CHANGELOG.md`.
   `tests/teste_base.py` confere.
5. **Dependência de execução fixa com `==`** e citada em `AVISOS_DE_TERCEIROS.md`. Nada AGPL/GPL
   dentro do pacote.
6. **Nada pessoal no repositório (ele é público).** Nenhuma digitalização real, IP/nome/serial de
   equipamento, caminho de usuário ou e-mail corporativo. Use `192.0.2.x` e nomes fictícios.
   `.gitignore` bloqueia `*.pdf` e imagens; a pasta `tesseract\` (binário de terceiros) fica fora do git.
   `tests/teste_higiene.py` confere.
7. **Todo uso do COM fica em `scanner/wia.py`** e todo HTTP de scanner em `scanner/escl.py`. O resto fala
   com a interface `Scanner` (`scanner/base.py`). Thread de trabalho chama `preparar_thread()` (CoInitialize).
8. **Testes nunca tocam nas preferências reais:** `tests/ajudantes.py` aponta
   `DIGITALIZARSCAN_CONFIG` para uma pasta temporária.

## Como testar

- `.venv\Scripts\python.exe tests\rodar_todos.py` (cada suite num processo próprio).
- A suíte não usa impressora: `ScannerFalso`, `tests/com_falso.py` (COM do WIA de mentira) e
  `tests/escl_falso.py` (servidor eSCL local). Hardware real só na mão.
- `teste_tema.py` roda com o plugin Qt `windows` (o `offscreen` ignora `setColorScheme`) e sem mostrar janela.
- `build.bat` roda tudo, empacota, confere o `.exe` e a janela.

## Armadilhas já encontradas

- **WIA + WSD = só a primeira folha do alimentador.** A automação do WIA (`Item.Transfer`) não baixa as
  demais páginas de um trabalho WIA 2.0; o scanner fica "ocupado". Por isso o eSCL (`scanner/escl.py`)
  existe e vem primeiro na lista. `Pages=0` no WSD dá E_INVALIDARG.
- **JPEG do alimentador da HP vem com altura 0 e marcador DNL (`FF DC`).** O Pillow não abre;
  `escl.corrigir_altura_jpeg` reescreve a altura no SOF.
- **Elementos do XML do eSCL em ordem de esquema:** fora de ordem, firmware estrito ignora o formato
  pedido e manda imagem crua (`application/octet-stream`).
- Pillow grava PDF de página 1-bit em CCITT, que não aceita `quality`: `saida/pdf.py` trata.
- `os.startfile` só na janela principal (o teste de higiene confere).
- Heredoc do Bash com texto longo/aspas quebrou várias vezes: gravar arquivos grandes com a ferramenta de escrita.
- `dist\` pode ficar travada por um processo invisível (programa aberto a partir da pasta): gerar em outra pasta.
