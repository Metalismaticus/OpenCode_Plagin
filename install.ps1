# install.ps1 - install the studio plugin (.opencode/) into a project folder.
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 "C:\path\to\game"
param(
    [Parameter(Mandatory = $true)]
    [string]$Project
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here ".opencode"

if (-not (Test-Path $src)) {
    Write-Output "ERROR: .opencode folder not found next to install.ps1 (repo broken?)"
    exit 1
}
if (-not (Test-Path $Project)) {
    Write-Output "ERROR: project folder not found: $Project"
    exit 1
}

$dst = Join-Path $Project ".opencode"
robocopy $src $dst /MIR /NFL /NDL /NJH | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Output "ERROR: copy failed (robocopy code $LASTEXITCODE)"
    exit 1
}

Write-Output "OK: studio installed -> $dst"

# quick sanity: hooks self-test inside the project (needs python on PATH)
$selftest = Join-Path $dst "studio\hooks\selftest.py"
try {
    $out = & python -X utf8 $selftest --quick 2>&1 | Select-Object -Last 1
    Write-Output "selftest: $out"
} catch {
    Write-Output "selftest: SKIPPED (python not found on PATH - hooks will not work)"
}

Write-Output ""
Write-Output "Next: open a NEW chat in the project folder and run  /studio/setup"
