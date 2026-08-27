# ClinicOne clinic_emar runtime schema synchronization
# Targeted to the Windows/Odoo/database paths evidenced by the supplied runtime log.
# Run in PowerShell AFTER stopping the normal Odoo Windows service/process.

$ErrorActionPreference = "Stop"

$OdooRoot = "C:\Program Files\Odoo 19.0.20260505"
$PythonExe = Join-Path $OdooRoot "python\python.exe"
$OdooBin = Join-Path $OdooRoot "server\odoo-bin"
$ConfigFile = Join-Path $OdooRoot "server\odoo.conf"
$Database = "odoo19ce"
$AddonRoot = "D:\projects\odoo19v\clinic19a"
$EmarRoot = Join-Path $AddonRoot "clinic_emar"
$Manifest = Join-Path $EmarRoot "__manifest__.py"
$UpgradeLog = Join-Path $AddonRoot "clinic_emar_upgrade_recovery.log"

Write-Host "ClinicOne clinic_emar schema synchronization"
Write-Host "Database : $Database"
Write-Host "Addon    : $EmarRoot"
Write-Host "Log      : $UpgradeLog"
Write-Host ""

foreach ($RequiredPath in @($PythonExe, $OdooBin, $ConfigFile, $Manifest)) {
    if (-not (Test-Path $RequiredPath)) {
        throw "Required path not found: $RequiredPath"
    }
}

$ManifestText = Get-Content $Manifest -Raw
if ($ManifestText -notmatch '19\.0\.3\.0\.0') {
    throw "clinic_emar manifest is not full-corrected version 19.0.3.0.0. Replace the addon folder first."
}

$ConfigSource = Join-Path $EmarRoot "models\integrations\res_config_settings.py"
if (-not (Test-Path $ConfigSource)) {
    throw "Schema-safe eMAR configuration source not found: $ConfigSource"
}
$ConfigText = Get-Content $ConfigSource -Raw
if ($ConfigText -notmatch 'store=False' -or $ConfigText -notmatch '_emar_write_parameter_values') {
    throw "clinic_emar company configuration is not the schema-safe 19.0.3.0.0 implementation."
}

# Refuse to run while the same Odoo installation is still serving.
$RunningTarget = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and
    $_.CommandLine -like "*Odoo 19.0.20260505*" -and
    ($_.Name -match "python|odoo")
}
if ($RunningTarget) {
    Write-Host ""
    Write-Host "A target Odoo process is still running:" -ForegroundColor Yellow
    $RunningTarget | Select-Object ProcessId, Name, CommandLine | Format-List
    throw "Stop the Odoo 19.0.20260505 service/process, then run this script again."
}

if (Test-Path $UpgradeLog) {
    Remove-Item $UpgradeLog -Force
}

Write-Host "Running controlled module upgrade..." -ForegroundColor Cyan

& $PythonExe $OdooBin `
    -c $ConfigFile `
    -d $Database `
    -u clinic_emar `
    --stop-after-init `
    --logfile=$UpgradeLog `
    --log-level=info

$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -ne 0) {
    Write-Host "clinic_emar upgrade FAILED with exit code $ExitCode." -ForegroundColor Red
    Write-Host "Open: $UpgradeLog"
    exit $ExitCode
}

$FatalPatterns = @(
    "Traceback \(most recent call last\)",
    "UndefinedColumn",
    "UndefinedTable",
    "__bases__ assignment",
    "Failed to load registry",
    "ParseError"
)

$FatalHits = @()
if (Test-Path $UpgradeLog) {
    foreach ($Pattern in $FatalPatterns) {
        $Hits = Select-String -Path $UpgradeLog -Pattern $Pattern
        if ($Hits) {
            $FatalHits += $Hits
        }
    }
}

if ($FatalHits.Count -gt 0) {
    Write-Host "The command exited 0 but fatal-looking log entries were found:" -ForegroundColor Yellow
    $FatalHits | Select-Object -First 30 | Format-Table -AutoSize
    Write-Host "Review the complete log before restarting Odoo: $UpgradeLog"
    exit 2
}

Write-Host "clinic_emar module upgrade completed without detected fatal patterns." -ForegroundColor Green
Write-Host "Now restart the normal Odoo 19.0.20260505 service and open the database."
Write-Host "Upgrade log: $UpgradeLog"
