# -*- coding: utf-8 -*-
# تشغيل شات بوت قانون العمل على ويندوز.
#   .\run.ps1              تشغيل عادي على 127.0.0.1:8000
#   .\run.ps1 -Port 8001   بورت مختلف
#   .\run.ps1 -Rebuild     يعيد بناء فهرس الـ embeddings قبل التشغيل
#   .\run.ps1 -Force       يقفل أي سيرفر شايل البورت ويشغّل مكانه

param(
    [int]$Port = 8000,
    [string]$AppHost = '127.0.0.1',
    [switch]$Rebuild,
    [switch]$NoReload,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

function Fail($msg) { Write-Host "`n[X] $msg`n" -ForegroundColor Red; exit 1 }
function Ok($msg)   { Write-Host "[/] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }

# 1) بايثون موجود؟
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Fail 'مفيش python في الـ PATH. نزّله من python.org وافتح terminal جديد.' }
Ok "python: $py"

# 2) ملف .env موجود؟ ومفتاحه حقيقي مش قالب؟
if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Fail 'عملت .env من القالب — افتحه وحط مفتاح OpenAI الحقيقي، وبعدين شغّل تاني.'
}
$keyLine = Select-String -Path '.env' -Pattern '^\s*OPENAI_API_KEY\s*=' | Select-Object -First 1
if (-not $keyLine) { Fail 'مفيش سطر OPENAI_API_KEY في .env' }
$key = ($keyLine.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
if ($key.Length -lt 20 -or $key -match '^sk-\.*$') {
    Fail 'المفتاح في .env لسه القالب (sk-...). حط مفتاحك الحقيقي من platform.openai.com/api-keys'
}
Ok "المفتاح موجود (طوله $($key.Length) حرف)"

# 3) المكتبات
python -c "import fastapi, uvicorn, openai, numpy" 2>$null
if (-not $?) {
    Warn 'ناقص مكتبات — بنزّلها...'
    python -m pip install -q -r requirements.txt
    if (-not $?) { Fail 'فشل تنزيل المكتبات.' }
}
Ok 'المكتبات تمام'

# 4) فهرس الـ embeddings — من غيره البحث بيبقى BM25 لوحده وبيضعف جدًا
$index = Join-Path 'data' 'embeddings.npz'
if ($Rebuild -and (Test-Path $index)) { Remove-Item $index -Force }
if (-not (Test-Path $index)) {
    Warn 'الفهرس مش موجود — بنبنيه (مرة واحدة، أقل من دقيقة وتكلفته سنتات).'
    python scripts/build_index.py
    if (-not $?) { Fail 'فشل بناء الفهرس.' }
}
$mb = [math]::Round((Get-Item $index).Length / 1MB, 1)
Ok "الفهرس جاهز ($mb ميجا)"

# 5) البورت فاضي؟
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $pidBusy = $busy[0].OwningProcess
    $owner = (Get-Process -Id $pidBusy -ErrorAction SilentlyContinue).ProcessName
    if ($Force) {
        Warn "بنقفل $owner (PID $pidBusy) اللي شايل البورت $Port..."
        Stop-Process -Id $pidBusy -Force
        Start-Sleep -Milliseconds 700
    } else {
        Fail "البورت $Port مشغول بـ $owner (PID $pidBusy). استعمل:  .\run.ps1 -Force   أو   .\run.ps1 -Port 8001"
    }
}

Write-Host "`n>> http://$AppHost`:$Port   (Ctrl+C للإيقاف)`n" -ForegroundColor Cyan

$uvArgs = @('-m', 'uvicorn', 'app.server:app', '--host', $AppHost, '--port', "$Port")
if (-not $NoReload) { $uvArgs += '--reload' }
& python $uvArgs
