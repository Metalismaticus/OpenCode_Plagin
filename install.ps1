# Install studio without deleting unrelated project plugins or config.
param([Parameter(Mandatory = $true)][string]$Project)
$ErrorActionPreference = "Stop"
$script = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "install.py"
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -X utf8 $script $Project
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -X utf8 $script $Project
} else {
    Write-Error "Python 3 is required for studio hooks. Install Python, then retry."
    exit 1
}
exit $LASTEXITCODE
