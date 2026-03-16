param(
    [string]$PythonExe = "C:\Users\User\miniforge3\python.exe",
    [switch]$RunEval
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}

$env:PYTHONPATH = "src"

Write-Host "Starting DPO training: Qwen3.5-2B"
pulsar train configs/examples/cam-dpo-qwen3.5-2b.yaml --task dpo

if ($RunEval) {
    Write-Host "Running eval on DPO adapter"
    pulsar eval --model ./outputs/cam-dpo-qwen3.5-2b/lora --test-data data/cam_intents_test.csv
}
