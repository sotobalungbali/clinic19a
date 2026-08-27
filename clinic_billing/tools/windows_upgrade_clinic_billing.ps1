param(
    [string]$OdooRoot = "C:\Program Files\Odoo 19.0.20260505",
    [string]$Database = "odoo19ce",
    [string]$Config = "",
    [string]$AddonRoot = "D:\projects\odoo19v\clinic19a"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Config)) {
    $Config = Join-Path $OdooRoot "server\odoo.conf"
}
$Python = Join-Path $OdooRoot "python\python.exe"
$OdooBin = Join-Path $OdooRoot "server\odoo-bin"
$Addon = Join-Path $AddonRoot "clinic_billing"
$Manifest = Join-Path $Addon "__manifest__.py"
$Log = Join-Path $AddonRoot "clinic_billing_upgrade.log"

Write-Host "ClinicOne clinic_billing targeted Odoo 19 upgrade"
Write-Host "Odoo      : $OdooRoot"
Write-Host "Database  : $Database"
Write-Host "Addon     : $Addon"
Write-Host "Log       : $Log"

foreach ($Required in @($Python, $OdooBin, $Config, $Manifest)) {
    if (-not (Test-Path $Required)) {
        throw "Required path not found: $Required"
    }
}

$ManifestText = Get-Content $Manifest -Raw
if ($ManifestText -notmatch '19\.0\.3\.0\.0') {
    throw "clinic_billing manifest is not the expected 19.0.3.0.0 release."
}

# The normal Odoo Windows service/process should be stopped before running this
# targeted schema/module update. We intentionally do not kill processes here.
$args = @(
    $OdooBin,
    "-c", $Config,
    "-d", $Database,
    "-u", "clinic_billing",
    "--stop-after-init",
    "--logfile", $Log
)

Write-Host "Running targeted update..."
& $Python @args
$ExitCode = $LASTEXITCODE
if ($ExitCode -ne 0) {
    throw "Odoo update returned exit code $ExitCode. Inspect $Log"
}

if (-not (Test-Path $Log)) {
    throw "Expected Odoo log was not created: $Log"
}

$CriticalPatterns = @(
    "Traceback \(most recent call last\)",
    "Failed to load registry",
    "ParseError:",
    "UndefinedColumn",
    "UndefinedTable",
    "__bases__ assignment",
    "ERROR .*clinic_billing"
)
$LogText = Get-Content $Log -Raw
$Found = @()
foreach ($Pattern in $CriticalPatterns) {
    if ($LogText -match $Pattern) {
        $Found += $Pattern
    }
}
if ($Found.Count -gt 0) {
    throw "Upgrade log contains critical pattern(s): $($Found -join ', '). Inspect $Log"
}

Write-Host "PASS: clinic_billing targeted update completed without detected critical errors."
Write-Host "Restart the normal Odoo service and perform the billing smoke scenarios."
