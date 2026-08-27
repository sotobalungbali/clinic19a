
$ErrorActionPreference = "Stop"

$OdooRoot = "C:\Program Files\Odoo 19.0.20260505"
$Python = Join-Path $OdooRoot "python\python.exe"
$OdooBin = Join-Path $OdooRoot "server\odoo-bin"
$Config = Join-Path $OdooRoot "server\odoo.conf"
$Database = "odoo19ce"

$AddonManifest = "D:\projects\odoo19v\clinic19a\clinic_membership\__manifest__.py"
$Log = "D:\projects\odoo19v\clinic19a\clinic_membership_install_v6.log"

if (-not (Test-Path $AddonManifest)) {
    throw "clinic_membership manifest not found: $AddonManifest"
}
if (-not (Select-String -Path $AddonManifest -Pattern "19.0.3.0.5" -Quiet)) {
    throw "Expected clinic_membership version 19.0.3.0.5"
}

& $Python $OdooBin `
    -c $Config `
    -d $Database `
    -i clinic_membership `
    --stop-after-init `
    --logfile=$Log

if ($LASTEXITCODE -ne 0) {
    throw "Odoo install failed. Review $Log"
}

$bad = Select-String `
    -Path $Log `
    -Pattern "Traceback|CRITICAL|Failed to load registry|UndefinedColumn|UndefinedTable|ParseError|Invalid view" `
    -SimpleMatch:$false

if ($bad) {
    $bad | Out-Host
    throw "Critical pattern found in $Log"
}

Write-Host "clinic_membership targeted install completed without detected critical errors." -ForegroundColor Green

