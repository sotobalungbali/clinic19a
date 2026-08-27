param(
    [string]$OdooRoot = "C:\Program Files\Odoo 19.0.20260505",
    [string]$ConfigPath = "C:\Program Files\Odoo 19.0.20260505\server\odoo.conf",
    [string]$Database = "odoo19ce",
    [string]$AddonRoot = "D:\projects\odoo19v\clinic19a"
)

$ErrorActionPreference = "Stop"

$Python = Join-Path $OdooRoot "python\python.exe"
$OdooBin = Join-Path $OdooRoot "server\odoo-bin"
$Manifest = Join-Path $AddonRoot "clinic_package\__manifest__.py"
$LogFile = Join-Path $AddonRoot "clinic_package_upgrade.log"

if (-not (Test-Path $Python)) { throw "Python runtime not found: $Python" }
if (-not (Test-Path $OdooBin)) { throw "odoo-bin not found: $OdooBin" }
if (-not (Test-Path $ConfigPath)) { throw "Odoo config not found: $ConfigPath" }
if (-not (Test-Path $Manifest)) { throw "clinic_package manifest not found: $Manifest" }

$ManifestText = Get-Content $Manifest -Raw
if ($ManifestText -notmatch "19\.0\.3\.0\.0") {
    throw "Expected clinic_package version 19.0.3.0.0 is not present in the target manifest."
}

Write-Host "IMPORTANT: stop the normal Odoo service/process before running this targeted upgrade."
Write-Host "Database: $Database"
Write-Host "Addon root: $AddonRoot"
Write-Host "Log: $LogFile"

& $Python $OdooBin `
    -c $ConfigPath `
    -d $Database `
    -u clinic_package `
    --stop-after-init `
    --logfile=$LogFile

if ($LASTEXITCODE -ne 0) {
    throw "clinic_package upgrade exited with code $LASTEXITCODE. Inspect $LogFile"
}

$CriticalPatterns = @(
    "Traceback \(most recent call last\)",
    "ParseError",
    "UndefinedColumn",
    "UndefinedTable",
    "Failed to load registry",
    "CRITICAL"
)

$Found = @()
foreach ($Pattern in $CriticalPatterns) {
    $Match = Select-String -Path $LogFile -Pattern $Pattern -SimpleMatch:$false
    if ($Match) { $Found += $Match }
}

if ($Found.Count -gt 0) {
    Write-Host "Critical pattern(s) detected:" -ForegroundColor Red
    $Found | Select-Object -First 30 | ForEach-Object { Write-Host $_.Line }
    throw "Upgrade log contains critical errors. Do not start normal Odoo yet."
}

Write-Host "clinic_package targeted upgrade completed without detected critical patterns." -ForegroundColor Green
Write-Host "Start normal Odoo, then perform UI/security/workflow/eMAR smoke tests."
