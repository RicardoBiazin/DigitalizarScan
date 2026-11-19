# Baixa o Tesseract OCR e monta a pasta "tesseract" que o programa (e o .spec) usam.
#
#   powershell -ExecutionPolicy Bypass -File ferramentas\baixar_tesseract.ps1
#
# 1. winget baixa o instalador oficial (tesseract-ocr.tesseract, Apache-2.0) para uma pasta
#    temporaria nova. NADA e' instalado no Windows: o instalador e' so' extraido com o 7z.
# 2. Copia tesseract.exe, as DLLs e os arquivos de configuracao para tesseract\.
# 3. Baixa os idiomas (tessdata_fast: por, eng, spa, chi_sim, osd) e confere o SHA256 de cada um.
#
# A pasta tesseract\ NAO entra no git (binario de terceiros, ~110 MB). O build.bat avisa
# se ela nao existir: o executavel sai sem OCR embutido.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$destino = Join-Path $raiz "tesseract"
$trabalho = Join-Path $env:TEMP ("dscan-tess-" + [guid]::NewGuid().ToString("N").Substring(0, 8))

# Hashes dos modelos de idioma (tessdata_fast, conferidos em 19/11/2026). Se o upstream
# publicar um modelo novo o script para: confira o arquivo e atualize o hash conscientemente.
$idiomas = @{
    "por" = "C4932B937207A9514B7514D518B931A99938C02A28A5A5A553F8599ED58B7DEB"
    "eng" = "7D4322BD2A7749724879683FC3912CB542F19906C83BCC1A52132556427170B2"
    "osd" = "9CF5D576FCC47564F11265841E5CA839001E7E6F38FF7F7AACF46D15A96B00FF"
    "spa" = "6F2E04D02774A18F01BED44B1111F2CD7F3BA7AC9DC4373CD3F898A40EA6B464"
    "chi_sim" = "A5FCB6F0DB1E1D6D8522F39DB4E848F05984669172E584E8D76B6B3141E1F730"
}

$sete = (Get-Command 7z -ErrorAction SilentlyContinue)
if (-not $sete) {
    foreach ($c in "C:\Program Files\7-Zip\7z.exe", "$env:USERPROFILE\scoop\shims\7z.exe") {
        if (Test-Path $c) { $sete = Get-Item $c; break }
    }
}
if (-not $sete) { throw "7-Zip nao encontrado. Instale o 7-Zip (winget install 7zip.7zip) e rode de novo." }
$sete = if ($sete.Source) { $sete.Source } else { $sete.FullName }

New-Item -ItemType Directory -Path $trabalho | Out-Null
try {
    $baixado = Join-Path $trabalho "instalador"
    New-Item -ItemType Directory -Path $baixado | Out-Null
    winget download --id tesseract-ocr.tesseract --exact --accept-package-agreements `
        --accept-source-agreements -d $baixado
    if ($LASTEXITCODE -ne 0) { throw "winget download falhou (codigo $LASTEXITCODE)" }
    $instalador = Get-ChildItem $baixado -Filter *.exe | Select-Object -First 1
    if (-not $instalador) { throw "o winget nao entregou um instalador" }

    $extraido = Join-Path $trabalho "extraido"
    & $sete x -y "-o$extraido" $instalador.FullName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "7z falhou ao extrair o instalador" }

    if (Test-Path $destino) { Remove-Item -LiteralPath $destino -Recurse -Force }
    New-Item -ItemType Directory -Path $destino | Out-Null
    Copy-Item (Join-Path $extraido "tesseract.exe") $destino
    Copy-Item (Join-Path $extraido "*.dll") $destino
    $tessdata = Join-Path $destino "tessdata"
    New-Item -ItemType Directory -Path $tessdata | Out-Null
    foreach ($item in "configs", "tessconfigs", "pdf.ttf") {
        Copy-Item (Join-Path $extraido "tessdata\$item") $tessdata -Recurse
    }

    foreach ($lingua in $idiomas.Keys) {
        $arquivo = Join-Path $tessdata "$lingua.traineddata"
        Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$lingua.traineddata" `
            -OutFile $arquivo -UseBasicParsing
        $hash = (Get-FileHash $arquivo -Algorithm SHA256).Hash
        if ($hash -ne $idiomas[$lingua]) {
            Remove-Item -LiteralPath $destino -Recurse -Force
            throw "SHA256 de $lingua.traineddata nao confere ($hash). Confira o arquivo e atualize o script."
        }
    }

    # Licencas que precisam acompanhar o binario.
    Get-ChildItem (Join-Path $extraido "doc") -File -ErrorAction SilentlyContinue |
        Copy-Item -Destination $destino

    & (Join-Path $destino "tesseract.exe") --version
    Write-Host "OK: $destino"
}
finally {
    Remove-Item -LiteralPath $trabalho -Recurse -Force -ErrorAction SilentlyContinue
}
