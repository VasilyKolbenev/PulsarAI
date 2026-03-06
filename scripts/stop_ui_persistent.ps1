param(
    [int]$Port = 18088
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-ListenerPid([int]$TargetPort) {
    $line = netstat -ano | Select-String (":$TargetPort") | Select-String "LISTENING" | Select-Object -First 1
    if (-not $line) {
        return $null
    }
    $parts = ($line.ToString() -replace "\s+", " ").Trim().Split(" ")
    if ($parts.Length -lt 5) {
        return $null
    }
    return [int]$parts[-1]
}

$runDir = Join-Path $root "outputs\runtime"
$pidFile = Join-Path $runDir "ui-$Port.pid"

$stopped = $false
if (Test-Path $pidFile) {
    $rawPid = (Get-Content $pidFile -Raw).Trim()
    if ($rawPid -match "^\d+$") {
        $pidFromFile = [int]$rawPid
        $proc = Get-Process -Id $pidFromFile -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $pidFromFile -Force -ErrorAction SilentlyContinue
            $stopped = $true
            Write-Host "Stopped PID from pidfile: $pidFromFile"
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$listenerPid = Get-ListenerPid -TargetPort $Port
if ($listenerPid) {
    Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
    $stopped = $true
    Write-Host "Stopped listener PID on port ${Port}: $listenerPid"
}

if (-not $stopped) {
    Write-Host "No running UI process found on port $Port"
} else {
    Write-Host "UI stop completed for port $Port"
}
