param(
    [string]$OdooRoot = "C:\Program Files\Odoo 19.0.20260505",
    [string]$Config = "C:\Program Files\Odoo 19.0.20260505\server\odoo.conf",
    [string]$Database = "odoo19ce",
    [string]$AddonRoot = "D:\projects\odoo19v\clinic19a"
)

$ErrorActionPreference = "Stop"
$ExpectedVersion = "19.0.3.0.0"
$Addon = Join-Path $AddonRoot "clinic_ap"
$Manifest = Join-Path $Addon "__manifest__.py"
$Python = Join-Path $OdooRoot "python\python.exe"
$OdooBin = Join-Path $OdooRoot "server\odoo-bin"
$Log = Join-Path $env:TEMP "clinic_ap_install_v1.log"

if (-not (Test-Path $Manifest)) { throw "clinic_ap manifest not found: $Manifest" }
if (-not (Select-String -Path $Manifest -Pattern $ExpectedVersion -Quiet)) { throw "Expected clinic_ap version $ExpectedVersion was not found." }
if (-not (Test-Path $Python)) { throw "Odoo Python not found: $Python" }
if (-not (Test-Path $OdooBin)) { throw "odoo-bin not found: $OdooBin" }

Write-Host "Stop the normal Odoo Windows service/process before running this targeted installer."
Write-Host "Installing clinic_ap $ExpectedVersion into database $Database ..."

& $Python $OdooBin -c $Config -d $Database -i clinic_ap --stop-after-init --logfile=$Log
$ExitCode = $LASTEXITCODE
if ($ExitCode -ne 0) {
    Write-Host "Odoo exited with code $ExitCode. Log: $Log"
    Get-Content $Log -Tail 160
    exit $ExitCode
}

$FatalPatterns = @(
    "Traceback",
    "ParseError",
    "AssertionError",
    "Invalid view",
    "UndefinedColumn",
    "UndefinedTable",
    "Failed to load registry",
    "CRITICAL"
)
$Fatal = Select-String -Path $Log -Pattern $FatalPatterns -SimpleMatch
if ($Fatal) {
    Write-Host "Potential fatal markers found in $Log"
    $Fatal | Select-Object -Last 30
    exit 2
}

Write-Host "clinic_ap targeted install completed without the configured fatal markers."
Write-Host "Log: $Log"

