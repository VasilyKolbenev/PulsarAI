param(
    [string]$BindHost = "127.0.0.1",
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
$healthUrl = "http://$BindHost`:$Port/api/v1/health"
$experimentsUrl = "http://$BindHost`:$Port/experiments"

$pidInFile = $null
if (Test-Path $pidFile) {
    $rawPid = (Get-Content $pidFile -Raw).Trim()
    if ($rawPid -match "^\d+$") {
        $pidInFile = [int]$rawPid
    }
}

$listenerPid = Get-ListenerPid -TargetPort $Port

Write-Host "Port: $Port"
Write-Host "PID file: $pidFile"
Write-Host "PID in file: $pidInFile"
Write-Host "Listener PID: $listenerPid"

if ($listenerPid) {
    $proc = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Process: $($proc.ProcessName) (PID=$listenerPid)"
    }
}

try {
    $health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 3
    Write-Host "Health: $($health.StatusCode)"
} catch {
    Write-Host "Health: DOWN"
}

try {
    $page = Invoke-WebRequest -UseBasicParsing -Uri $experimentsUrl -TimeoutSec 3
    Write-Host "Experiments route: $($page.StatusCode)"
} catch {
    Write-Host "Experiments route: DOWN"
}
