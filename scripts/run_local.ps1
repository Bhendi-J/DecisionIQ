# PowerShell launcher for Windows
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $ProjectRoot

# Add Python Scripts directory to PATH if uv was installed there
if (Test-Path "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\Scripts") {
    $env:Path = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\Scripts;$env:Path"
}

npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build

if ($env:INSTALL_PHISHING -eq "1") {
    python -m uv sync --locked --extra phishing
    python -m uv run --no-sync python -m scripts.install_phishing_model
} else {
    python -m uv sync --locked
}

if ($env:INSTALL_DEMO_DATA -ne "0") {
    python -m uv run --no-sync python -m scripts.install_demo_data
}

$port = if ($env:DECISIONIQ_PORT) { $env:DECISIONIQ_PORT } else { "8082" }
python -m uv run python -m uvicorn decisioniq.main:app --host 127.0.0.1 --port $port
