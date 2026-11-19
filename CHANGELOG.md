# Changelog

## [0.3.0] - 2026-11-19

Primeira versão pública (licença MIT).

- **Interface em 4 idiomas:** português, English, Español e 中文, escolhidos em Exibir > Idioma (ou
  automático, pelo idioma do Windows). A troca vale na hora, sem reiniciar. O OCR acompanha o idioma
  (português, inglês, espanhol, chinês simplificado). README nos 4 idiomas.
- **Tema:** claro, escuro ou do sistema (Exibir > Tema), lembrado entre as aberturas.
- **Papel no alimentador:** o scanner de rede informa se há papel; o programa mostra “Alimentador: com
  papel/vazio” e escolhe Alimentador ou Vidro quando o estado muda (a escolha manual vale até a próxima mudança).
- **Prévia do vidro:** botão “Prévia…” mostra o vidro inteiro em baixa resolução; arrastar um retângulo
  digitaliza só aquela área (eSCL e WIA).
- Licença MIT, `LICENSE` e avisos de terceiros revisados. Nenhum dado de equipamento ou rede no código.

## [0.2.2]

- Abre o JPEG que o alimentador de impressoras HP manda pelo eSCL: altura 0 no cabeçalho e as linhas
  num marcador DNL no fim, que o Pillow recusa. O cabeçalho é corrigido antes de abrir.

## [0.2.1]

- Pedido eSCL na ordem de elementos do esquema (fora de ordem, firmware estrito manda imagem crua).
- Leitura de imagem crua e de JPEG dentro de PDF; resposta desconhecida fica salva para diagnóstico.
- Resolução limitada ao que a origem aceita; a página guarda a resolução real.

## [0.2.0]

- **Digitalização pela rede via eSCL (AirScan):** todas as folhas do alimentador, frente e verso e vidro,
  sem depender do WIA. Descoberta por mDNS, portas TCP/IP das impressoras do Windows e nome do dispositivo
  WSD; botão “Adicionar pelo endereço…”.
- O WIA com impressora de rede por WSD entrega só a primeira folha do alimentador: por isso o eSCL vem
  primeiro na lista.

## [0.1.3] – [0.1.1]

- Correções do WIA com drivers WSD: item único “Scan”, origem no dispositivo, uma folha por transferência,
  scanner “ocupado” tratado com espera, fim do lote, Ajuda > Diagnóstico do scanner.

## [0.1.0]

Primeira versão.

- Digitalização pelo WIA do Windows: vidro, alimentador automático e frente e verso (quando o driver
  oferece), cor / cinza / preto e branco, 150 a 600 dpi, A4 / Carta / Ofício / área total.
- Miniaturas das páginas com girar, excluir, mover e arrastar para reordenar.
- Saída em PDF multipágina, JPG ou PNG, com gravação atômica.
- OCR com o Tesseract (português e inglês): PDF pesquisável. Sem o Tesseract, o PDF sai sem texto.
- Preferências lembradas em `%APPDATA%\DigitalizarScan`.
