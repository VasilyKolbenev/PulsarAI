param(
    [string]$PythonExe = "C:\Users\User\miniforge3\python.exe",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 18088,
    [string]$EnvFile = ".env.demo.example",
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}
if (-not (Test-Path $EnvFile)) {
    throw "Env profile not found: $EnvFile"
}

$env:PYTHONPATH = "src"
$env:FORGE_ENV_FILE = (Resolve-Path $EnvFile).Path
$env:FORGE_STAND_MODE = "demo"
$env:FORGE_AUTH_ENABLED = "false"
if (-not $env:FORGE_CORS_ORIGINS) {
    $env:FORGE_CORS_ORIGINS = "http://$BindHost`:$Port"
}

Write-Host "[1/2] Bootstrapping investor demo data..."
& $PythonExe scripts/investor_demo_bootstrap.py

Write-Host "[2/2] Starting persistent demo UI..."
$startScript = Join-Path $root "scripts\start_ui_persistent.ps1"
if ($ForceRestart) {
    & $startScript -PythonExe $PythonExe -BindHost $BindHost -Port $Port -EnvFile $EnvFile -StandMode "demo" -ForceRestart
} else {
    & $startScript -PythonExe $PythonExe -BindHost $BindHost -Port $Port -EnvFile $EnvFile -StandMode "demo"
}
