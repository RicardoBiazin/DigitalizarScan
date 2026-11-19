# DigitalizarScan

[Português](README.md) · [English](README.en.md) · **Español** · [中文](README.zh-CN.md)

Programa de escritorio para Windows que escanea documentos directamente desde la impresora multifunción,
reúne las páginas, reconoce el texto (OCR) y guarda un PDF con texto buscable, JPG o PNG.
Licencia [MIT](LICENSE).

## Qué hace

- **Escanea por la red** (eSCL/AirScan, el protocolo de la mayoría de las multifunciones HP, Canon, Epson y
  Brother recientes) **o con WIA** de Windows (escáneres USB y controladores del fabricante).
- **Todas las hojas del alimentador automático**, doble cara y cristal. Color, escala de grises o blanco y
  negro; de 75 a 1200 ppp según el equipo; A4, Carta, Oficio o el área total del cristal.
- **Vista previa del cristal** con selección de un área, para escanear solo una parte.
- **Indicador de papel en el alimentador**: muestra si hay papel y elige Alimentador o Cristal por sí solo.
- **Organiza las páginas**: girar, mover, eliminar, arrastrar para reordenar, abrir una página.
- **Guarda** en PDF (un archivo), JPG o PNG, sin dejar nunca un archivo a medias sobre otro existente.
- **OCR** con Tesseract incluido (portugués, inglés, español y chino simplificado): el PDF sale con texto
  seleccionable y buscable.
- **Interfaz en 4 idiomas** (Português, English, Español, 中文) y **tema** claro, oscuro o del sistema.

## Cómo se usa

1. Encienda la multifunción y abra `DigitalizarScan.exe`.
2. Elija el escáner. Los de red aparecen como «… — red (IP)»; los de WIA, como «… — WIA». Si su impresora no
   aparece sola, use **Añadir por dirección…** y escriba su IP.
3. Elija el origen, el color, la resolución y el papel. Pulse **Escanear**. Para añadir más páginas, púlselo
   de nuevo.
4. En el cristal, **Vista previa…** muestra todo el cristal: arrastre un rectángulo y use **Usar esta área**.
5. Ajuste las páginas, elija el formato, marque **Reconocer texto (OCR)** si lo desea y pulse **Guardar…**.

Menú **Ver**: tema (sistema, claro, oscuro) e idioma. **Ayuda > Diagnóstico del escáner** escribe un
`diagnostico.txt` con lo que informa el equipo, útil para reportar un problema.

Sin escáner a mano, `DigitalizarScan.exe --demo` usa un escáner de demostración.

## Requisitos

- Windows 10 u 11 (64 bits).
- Multifunción de red con eSCL/AirScan (recomendado: entrega todas las hojas del alimentador) o cualquier
  escáner que aparezca en *Dispositivos de imagen* (WIA). Con una impresora de red instalada por WSD, WIA
  solo entrega la primera hoja del alimentador; por eso eSCL va primero en la lista.
- El OCR usa el Tesseract incluido en el paquete. Sin él, el PDF sale sin texto y el programa lo avisa.

Descargue el ZIP de la [última versión](../../releases/latest), extraiga la carpeta completa y abra
`DigitalizarScan.exe`.

## Desarrollo

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File ferramentas\baixar_tesseract.ps1   # OCR (opcional)
.venv\Scripts\python.exe app.py --demo
.venv\Scripts\python.exe tests\rodar_todos.py
build.bat
```

`build.bat` ejecuta las pruebas, empaqueta con PyInstaller (una carpeta), comprueba el ejecutable
(`--autoverificacao`), abre la ventana de verdad (prueba de humo) y genera el ZIP en `dist\`. Las pruebas no
necesitan impresora: usan un escáner falso, un COM de WIA simulado y un servidor eSCL local.

El código fuente está en portugués (nombres y comentarios); los textos de pantalla están en
`digitalizarscan/idiomas/`. Para añadir un idioma: copie `digitalizarscan/idiomas/en.py`, tradúzcalo y
registre el código en `digitalizarscan/i18n.py`; `tests/teste_idiomas.py` comprueba que no falte ninguna clave.

## Límites conocidos

- La interfaz y los README en inglés, español y chino se tradujeron sin revisión de un hablante nativo;
  las correcciones son bienvenidas.
- El doble cara por WIA depende de que el controlador lo ofrezca; por eSCL, de la impresora.
- Probado en equipo real con una HP OfficeJet Pro 7740 (eSCL). Otros modelos siguen el mismo estándar, pero
  pueden tener particularidades; el archivo de diagnóstico ayuda a tratarlas.

## Licencia

[MIT](LICENSE). Los componentes de terceros (Qt for Python, pywin32, Pillow, Tesseract) están en
[AVISOS_DE_TERCEIROS.md](AVISOS_DE_TERCEIROS.md).
