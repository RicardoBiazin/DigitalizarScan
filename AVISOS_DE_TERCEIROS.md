# Avisos de terceiros / Third-party notices

O DigitalizarScan (licença MIT) usa os componentes abaixo. Cada um mantém a sua licença.
DigitalizarScan (MIT license) uses the components below. Each keeps its own license.

| Componente | Versão | Licença | Uso |
|---|---|---|---|
| PySide6-Essentials (Qt for Python) | 6.12.0 | LGPL-3.0 | Interface gráfica. Bibliotecas dinâmicas na pasta `_internal`, substituíveis por versões compatíveis. |
| pywin32 | 312 | PSF | Acesso ao WIA (COM) do Windows. |
| Pillow | 13.0.0 | MIT-CMU (HPND) | Imagens, PDF e JPG/PNG. |
| Tesseract OCR | 5.5.3 | Apache-2.0 | Reconhecimento de texto. Executado como processo separado, na pasta `tesseract\`. |
| tessdata_fast (por, eng, spa, chi_sim, osd) | principal | Apache-2.0 | Modelos de idioma do Tesseract. |
| PyInstaller | 6.22.3 | GPL-2.0 com exceção para o programa empacotado | Só no empacotamento; não faz parte do programa. |
| pypdf | 7.1.1 | BSD-3-Clause | Só na suíte de testes (confere o texto do PDF pesquisável). |

O Tesseract e as bibliotecas que o acompanham (Leptonica, libtiff, libpng, libjpeg-turbo e
outras) vêm do instalador oficial do projeto, extraído por `ferramentas/baixar_tesseract.ps1`.
Os textos de licença desse instalador acompanham o binário na pasta `tesseract\`.

Qt for Python e Qt são licenciados sob LGPL-3.0: o código-fonte do Qt está disponível em
<https://www.qt.io/download-open-source>. / Qt source code is available at the address above.
