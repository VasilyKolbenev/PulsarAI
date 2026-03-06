param(
    [string]$PythonExe = "C:\Users\User\miniforge3\python.exe",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 18088,
    [string]$EnvFile = ".env.demo.example",
    [string]$StandMode = "demo",
    [switch]$AuthEnabled,
    [switch]$ForceRestart
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

if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}
if (-not (Test-Path $EnvFile)) {
    throw "Env profile not found: $EnvFile"
}

$runDir = Join-Path $root "outputs\runtime"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$pidFile = Join-Path $runDir "ui-$Port.pid"
$outLog = Join-Path $runDir "ui-$Port.out.log"
$errLog = Join-Path $runDir "ui-$Port.err.log"

$healthUrl = "http://$BindHost`:$Port/api/v1/health"
$experimentsUrl = "http://$BindHost`:$Port/experiments"
$corsOrigins = "http://$BindHost`:$Port"

$listenerPid = Get-ListenerPid -TargetPort $Port
if ($listenerPid) {
    if ($ForceRestart) {
        Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        $listenerAfterRestart = Get-ListenerPid -TargetPort $Port
        if ($listenerAfterRestart) {
            throw "Port $Port is still occupied by PID $listenerAfterRestart. Stop it manually (possibly requires admin) and rerun."
        }
    } else {
        try {
            $health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 1
            $experiments = Invoke-WebRequest -UseBasicParsing -Uri $experimentsUrl -TimeoutSec 1
            if ($health.StatusCode -eq 200 -and $experiments.StatusCode -eq 200) {
                $listenerPid | Set-Content -Path $pidFile -Encoding ascii
                Write-Host "UI already running and healthy on port $Port"
                Write-Host "Open: http://$BindHost`:$Port/experiments"
                exit 0
            }
        } catch {
        }

        throw "Port $Port is occupied by PID $listenerPid. Run with -ForceRestart to replace stale process."
    }
}

if (Test-Path $outLog) {
    Remove-Item $outLog -Force
}
if (Test-Path $errLog) {
    Remove-Item $errLog -Force
}

# Workaround for Windows environment collision (Path/PATH duplicate keys)
$safePath = [Environment]::GetEnvironmentVariable("Path", "Process")
if (-not $safePath) {
    $safePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
}
try {
    Remove-Item Env:PATH -ErrorAction SilentlyContinue
} catch {
}
try {
    Remove-Item Env:Path -ErrorAction SilentlyContinue
} catch {
}
if ($safePath) {
    $env:Path = $safePath
}

$args = @(
    "scripts/run_ui_server.py",
    "--host", $BindHost,
    "--port", $Port,
    "--env-file", $EnvFile,
    "--stand-mode", $StandMode,
    "--cors-origins", $corsOrigins
)
if ($AuthEnabled) {
    $args += "--auth-enabled"
} else {
    $args += "--auth-disabled"
}

$proc = Start-Process -FilePath $PythonExe -ArgumentList $args -WorkingDirectory $root -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
$proc.Id | Set-Content -Path $pidFile -Encoding ascii

$healthy = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    $alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $alive) {
        break
    }
    try {
        $health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 1
        if ($health.StatusCode -eq 200) {
            $experiments = Invoke-WebRequest -UseBasicParsing -Uri $experimentsUrl -TimeoutSec 1
            if ($experiments.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        }
    } catch {
    }
}

if (-not $healthy) {
    Write-Host "UI failed to become healthy on port $Port"
    if (Test-Path $errLog) {
        Write-Host "--- stderr tail ---"
        Get-Content $errLog -Tail 80
    }
    if (Test-Path $outLog) {
        Write-Host "--- stdout tail ---"
        Get-Content $outLog -Tail 80
    }
    throw "Startup failed"
}

Write-Host "UI started successfully"
Write-Host "PID: $($proc.Id)"
Write-Host "Health: $healthUrl"
Write-Host "Open: http://$BindHost`:$Port/experiments"
Write-Host "Logs: $outLog / $errLog"
