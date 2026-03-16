param(
    [string]$PythonExe = "C:\Users\User\miniforge3\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}

Write-Host "[1/5] Python version"
& $PythonExe --version

Write-Host "[2/5] Install Python deps (editable + ui + dev)"
& $PythonExe -m pip install -e ".[ui,dev]"

Write-Host "[3/5] Install Node deps (root)"
cmd /c npm install

Write-Host "[4/5] Install Node deps (ui)"
cmd /c npm --prefix ui install

Write-Host "[5/5] Sanity checks"
& $PythonExe -c "import torch, transformers, trl, peft, datasets; print('torch', torch.__version__)"
pulsar --help | Out-Null
Write-Host "Environment setup complete."
