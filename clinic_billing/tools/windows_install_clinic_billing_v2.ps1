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
$Log = Join-Path $AddonRoot "clinic_billing_install_v2.log"

foreach ($Required in @($Python, $OdooBin, $Config, $Manifest)) {
    if (-not (Test-Path $Required)) { throw "Required path not found: $Required" }
}

$ManifestText = Get-Content $Manifest -Raw
if ($ManifestText -notmatch '19\.0\.3\.0\.1') {
    throw "clinic_billing manifest is not expected release 19.0.3.0.1."
}

$args = @(
    $OdooBin,
    "-c", $Config,
    "-d", $Database,
    "-i", "clinic_billing",
    "--stop-after-init",
    "--logfile", $Log
)

& $Python @args
if ($LASTEXITCODE -ne 0) {
    throw "Odoo install returned exit code $LASTEXITCODE. Inspect $Log"
}

$CriticalPatterns = @(
    "Traceback \(most recent call last\)",
    "Failed to load registry",
    "ParseError:",
    "AssertionError:",
    "Invalid view",
    "UndefinedColumn",
    "UndefinedTable",
    "CRITICAL",
    "ERROR .*clinic_billing"
)
$LogText = Get-Content $Log -Raw
$Found = @()
foreach ($Pattern in $CriticalPatterns) {
    if ($LogText -match $Pattern) { $Found += $Pattern }
}
if ($Found.Count -gt 0) {
    throw "Install log contains critical pattern(s): $($Found -join ', '). Inspect $Log"
}
Write-Host "PASS: clinic_billing targeted install completed without detected critical errors."
