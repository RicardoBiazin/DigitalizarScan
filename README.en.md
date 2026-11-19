# DigitalizarScan

[Português](README.md) · **English** · [Español](README.es.md) · [中文](README.zh-CN.md)

A Windows desktop program that scans documents straight from your multifunction printer, gathers the
pages, recognizes the text (OCR) and saves a searchable PDF, JPG or PNG. [MIT](LICENSE) license.

## What it does

- **Scans over the network** (eSCL/AirScan, the protocol of most recent HP, Canon, Epson and Brother
  multifunction printers) **or through Windows WIA** (USB scanners and manufacturer drivers).
- **Every sheet in the automatic document feeder**, both sides, and the glass. Color, grayscale or black
  and white; 75 to 1200 dpi depending on the device; A4, Letter, Legal or the full glass area.
- **Glass preview** with area selection, to scan only a part of the glass.
- **Feeder paper indicator**: shows whether there is paper and picks Feeder or Glass by itself.
- **Organizes the pages**: rotate, move, delete, drag to reorder, open a page.
- **Saves** as PDF (one file), JPG or PNG, never leaving a half-written file over an existing one.
- **OCR** with the bundled Tesseract (Portuguese, English, Spanish and Simplified Chinese): the PDF has
  selectable, searchable text.
- **Interface in 4 languages** (Português, English, Español, 中文) and a light, dark or system **theme**.

## How to use

1. Turn the printer on and open `DigitalizarScan.exe`.
2. Pick the scanner. Network ones show as “… — network (IP)”; WIA ones as “… — WIA”. If your printer does
   not show up by itself, use **Add by address…** and type its IP.
3. Choose the source, color, resolution and paper. Click **Scan**. To add more pages, click it again.
4. On the glass, **Preview…** shows the whole glass: drag a rectangle and use **Use this area**.
5. Adjust the pages, pick the format, tick **Recognize text (OCR)** if you want it, and click **Save…**.

**View** menu: theme (system, light, dark) and language. **Help > Scanner diagnostics** writes a
`diagnostico.txt` with what the device reports, handy for bug reports.

With no scanner at hand, `DigitalizarScan.exe --demo` uses a demo scanner.

## Requirements

- Windows 10 or 11 (64-bit).
- A network multifunction printer with eSCL/AirScan (recommended: it delivers every feeder sheet), or any
  scanner listed under *Imaging devices* (WIA). With a network printer installed through WSD, WIA only
  delivers the first feeder sheet, which is why eSCL comes first in the list.
- OCR uses the Tesseract bundled in the package. Without it the PDF has no text and the program warns you.

Download the ZIP of the [latest release](../../releases/latest), extract the whole folder and open
`DigitalizarScan.exe`.

## Development

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File ferramentas\baixar_tesseract.ps1   # OCR (optional)
.venv\Scripts\python.exe app.py --demo
.venv\Scripts\python.exe tests\rodar_todos.py
build.bat
```

`build.bat` runs the test suite, packages with PyInstaller (one folder), checks the executable
(`--autoverificacao`), opens the real window (smoke test) and builds the ZIP in `dist\`. The tests need no
printer: they use a fake scanner, a simulated WIA COM and a local eSCL server.

Source code is in Portuguese (names and comments); screen texts live in `digitalizarscan/idiomas/`.
To add a language: copy `digitalizarscan/idiomas/en.py`, translate it and register the code in
`digitalizarscan/i18n.py`; `tests/teste_idiomas.py` checks that no key is missing.

## Known limits

- The English, Spanish and Chinese interface and READMEs were translated without a native speaker's
  review; corrections are welcome.
- Duplex through WIA depends on the driver offering it; through eSCL, on the printer.
- Tested on real hardware with an HP OfficeJet Pro 7740 (eSCL). Other models follow the same standard but
  may have quirks; the diagnostics file helps to handle them.

## License

[MIT](LICENSE). Third-party components (Qt for Python, pywin32, Pillow, Tesseract) are listed in
[AVISOS_DE_TERCEIROS.md](AVISOS_DE_TERCEIROS.md).
