param(
    [string]$PythonExe = "C:\Users\User\miniforge3\python.exe",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 18888,
    [string]$EnvFile = ".env.prod-ready.example",
    [string]$ApiKeyName = "prod-dev-admin",
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
$env:PULSAR_ENV_FILE = (Resolve-Path $EnvFile).Path
$env:PULSAR_STAND_MODE = "prod-ready-dev"
$env:PULSAR_AUTH_ENABLED = "true"
if (-not $env:PULSAR_CORS_ORIGINS) {
    $env:PULSAR_CORS_ORIGINS = "http://$BindHost`:$Port"
}

Write-Host "[1/3] Preparing API key for prod-ready dev stand..."
$apiKey = (& $PythonExe -c "from pulsar_ai.ui.auth import ApiKeyStore; s=ApiKeyStore(); s.revoke('$ApiKeyName'); print(s.generate_key('$ApiKeyName'))").Trim()
if (-not $apiKey) {
    throw "Failed to generate API key"
}

$accessDir = Join-Path $root "outputs\access"
New-Item -ItemType Directory -Path $accessDir -Force | Out-Null
$keyPath = Join-Path $accessDir "$ApiKeyName.key"
Set-Content -Path $keyPath -Value $apiKey -Encoding UTF8

Write-Host "[2/3] Starting persistent prod-ready UI..."
$startScript = Join-Path $root "scripts\start_ui_persistent.ps1"
if ($ForceRestart) {
    & $startScript -PythonExe $PythonExe -BindHost $BindHost -Port $Port -EnvFile $EnvFile -StandMode "prod-ready-dev" -AuthEnabled -ForceRestart
} else {
    & $startScript -PythonExe $PythonExe -BindHost $BindHost -Port $Port -EnvFile $EnvFile -StandMode "prod-ready-dev" -AuthEnabled
}

Write-Host "[3/3] Access"
Write-Host "Health URL: http://$BindHost`:$Port/api/v1/health"
Write-Host "API key file: $keyPath"
Write-Host "Open URL once to persist key in browser: http://$BindHost`:$Port/?api_key=$apiKey"
