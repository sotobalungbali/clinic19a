param(
    [string]$OdooRoot = "C:\Program Files\Odoo 19.0.20260505",
    [string]$Config = "C:\Program Files\Odoo 19.0.20260505\server\odoo.conf",
    [string]$Database = "odoo19ce",
    [string]$AddonRoot = "D:\projects\odoo19v\clinic19a"
)

$ErrorActionPreference = "Stop"
$Manifest = Join-Path $AddonRoot "clinic_ar\__manifest__.py"
if (-not (Test-Path $Manifest)) { throw "clinic_ar manifest not found: $Manifest" }
if (-not (Select-String -Path $Manifest -Pattern '19\.0\.3\.0\.2' -Quiet)) { throw "Expected clinic_ar version 19.0.3.0.2" }

$Python = Join-Path $OdooRoot "python\python.exe"
$OdooBin = Join-Path $OdooRoot "server\odoo-bin"
$Log = Join-Path $env:TEMP "clinic_ar_install.log"

Write-Host "Stop the normal Odoo service/process before running this helper."
& $Python $OdooBin -c $Config -d $Database -i clinic_ar --stop-after-init --logfile=$Log
if ($LASTEXITCODE -ne 0) { throw "Odoo install returned exit code $LASTEXITCODE. See $Log" }

$bad = Select-String -Path $Log -Pattern 'Traceback|ParseError|AssertionError|Invalid view|UndefinedColumn|UndefinedTable|Failed to load registry|CRITICAL' -SimpleMatch:$false
if ($bad) {
    $bad | Format-Table -AutoSize
    throw "Potential runtime failure markers found. See $Log"
}
Write-Host "clinic_ar targeted install completed without known fatal markers. Log: $Log"



