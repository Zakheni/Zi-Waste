# Install sage_bridge as a Windows service (NSSM).
# Requires: 32-bit Python venv, System DSN, service account with company-folder rights.
# Example:
#   .\scripts\install_service.ps1 -Python "C:\sage_bridge\venv32\Scripts\python.exe" -WorkDir "C:\sage_bridge"

param(
    [string]$ServiceName = "sage_bridge",
    [string]$Python = "",
    [string]$WorkDir = "",
    [string]$Nssm = "nssm"
)

$ErrorActionPreference = "Stop"

if (-not $WorkDir) {
    $WorkDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if (-not $Python) {
    $venvPy = Join-Path $WorkDir "venv32\Scripts\python.exe"
    if (Test-Path $venvPy) {
        $Python = $venvPy
    } else {
        throw "Pass -Python pointing at 32-bit python.exe"
    }
}

$nssmCmd = Get-Command $Nssm -ErrorAction SilentlyContinue
if (-not $nssmCmd) {
    throw "NSSM not found. Install NSSM and re-run, or add it to PATH."
}

$appArgs = "-m app.main"

& $Nssm install $ServiceName $Python $appArgs
& $Nssm set $ServiceName AppDirectory $WorkDir
& $Nssm set $ServiceName DisplayName "Sage 50 Pastel Bridge"
& $Nssm set $ServiceName Start SERVICE_AUTO_START
& $Nssm set $ServiceName AppStdout (Join-Path $WorkDir "sage_bridge.out.log")
& $Nssm set $ServiceName AppStderr (Join-Path $WorkDir "sage_bridge.err.log")
& $Nssm set $ServiceName AppRotateFiles 1
& $Nssm set $ServiceName AppExit Default Restart
& $Nssm set $ServiceName AppRestartDelay 5000

Write-Host "Service $ServiceName installed. Set the Log On account to a user that can open the Pastel company and the 32-bit System DSN, then: nssm start $ServiceName"
