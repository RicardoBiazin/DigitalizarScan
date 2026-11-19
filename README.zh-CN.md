# DigitalizarScan

[Português](README.md) · [English](README.en.md) · [Español](README.es.md) · **中文**

一款 Windows 桌面程序：直接用多功能一体机扫描文档，合并页面，识别文字（OCR），并保存为可搜索的 PDF、JPG 或 PNG。
采用 [MIT](LICENSE) 许可证。

## 功能

- **通过网络扫描**（eSCL/AirScan，近年来大多数 HP、Canon、Epson、Brother 一体机使用的协议），**或通过 Windows 的 WIA**
  （USB 扫描仪和厂商驱动）。
- **自动进纸器中的每一页**、双面扫描和玻璃板。彩色、灰度或黑白；分辨率 75 至 1200 dpi（取决于设备）；
  A4、Letter、Legal 或整个玻璃板区域。
- **玻璃板预览**，可选择区域，只扫描其中一部分。
- **进纸器纸张指示**：显示是否有纸，并自动选择“进纸器”或“玻璃板”。
- **整理页面**：旋转、移动、删除、拖动排序、打开页面。
- **保存**为 PDF（单个文件）、JPG 或 PNG，绝不会在已有文件上留下写到一半的文件。
- **OCR**：内置 Tesseract（葡萄牙语、英语、西班牙语和简体中文），生成的 PDF 文字可选择、可搜索。
- **4 种界面语言**（Português、English、Español、中文），以及浅色、深色或跟随系统的**主题**。

## 使用方法

1. 打开一体机电源，运行 `DigitalizarScan.exe`。
2. 选择扫描仪。网络扫描仪显示为“… — 网络（IP）”，WIA 扫描仪显示为“… — WIA”。如果打印机没有自动出现，请使用
   **按地址添加…** 并输入它的 IP。
3. 选择来源、颜色、分辨率和纸张，点击**扫描**。要继续添加页面，再次点击即可。
4. 使用玻璃板时，**预览…** 会显示整个玻璃板：拖出一个矩形，然后点击**使用此区域**。
5. 调整页面，选择格式，需要时勾选**识别文字（OCR）**，然后点击**保存…**。

**查看**菜单：主题（跟随系统、浅色、深色）和语言。**帮助 > 扫描仪诊断**会生成 `diagnostico.txt`，记录设备报告的信息，
便于反馈问题。

手边没有扫描仪时，`DigitalizarScan.exe --demo` 会使用演示扫描仪。

## 系统要求

- Windows 10 或 11（64 位）。
- 支持 eSCL/AirScan 的网络一体机（推荐：可以取得进纸器中的每一页），或在“图像设备”中出现的任何扫描仪（WIA）。
  通过 WSD 安装的网络打印机，WIA 只能取得进纸器的第一页，因此列表中 eSCL 排在前面。
- OCR 使用软件包内置的 Tesseract。没有它时，PDF 不含文字，程序会给出提示。

从[最新版本](../../releases/latest)下载 ZIP，解压整个文件夹，然后运行 `DigitalizarScan.exe`。

## 开发

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File ferramentas\baixar_tesseract.ps1   # OCR（可选）
.venv\Scripts\python.exe app.py --demo
.venv\Scripts\python.exe tests\rodar_todos.py
build.bat
```

`build.bat` 会运行测试、用 PyInstaller 打包（单个文件夹）、检查可执行文件（`--autoverificacao`）、真正打开窗口
（冒烟测试），并在 `dist\` 中生成 ZIP。测试不需要打印机：使用模拟扫描仪、模拟的 WIA COM 和本地 eSCL 服务器。

源代码使用葡萄牙语（名称和注释）；界面文字位于 `digitalizarscan/idiomas/`。添加语言的方法：复制
`digitalizarscan/idiomas/en.py`，翻译后在 `digitalizarscan/i18n.py` 中注册语言代码；`tests/teste_idiomas.py`
会检查是否缺少任何键。

## 已知限制

- 英语、西班牙语和中文的界面与 README 未经母语者审校，欢迎提出修改意见。
- WIA 的双面扫描取决于驱动是否提供该模式；eSCL 则取决于打印机。
- 已在真实设备（HP OfficeJet Pro 7740，eSCL）上测试。其他型号遵循同一标准，但可能有各自的特殊情况；
  诊断文件有助于处理这些情况。

## 许可证

[MIT](LICENSE)。第三方组件（Qt for Python、pywin32、Pillow、Tesseract）见
[AVISOS_DE_TERCEIROS.md](AVISOS_DE_TERCEIROS.md)。
