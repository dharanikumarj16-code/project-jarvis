# ==============================================================================
# launch_jarvis.ps1 - JARVIS Autonomous System Launcher
# ==============================================================================
# 1. Activates Python Virtual Environment (.venv)
# 2. Ensures WSL Ollama service is reachable on 127.0.0.1:11434
# 3. Validates model readiness & launches JARVIS
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$Cyan    = "`e[96m"
$Green   = "`e[92m"
$Yellow  = "`e[93m"
$Red     = "`e[91m"
$Bold    = "`e[1m"
$Dim     = "`e[90m"
$Reset   = "`e[0m"

Write-Host ""
Write-Host "$Cyan$Bold╔══════════════════════════════════════════════════════════════════════╗$Reset"
Write-Host "$Cyan$Bold║                     J  A  R  V  I  S   O S                           ║$Reset"
Write-Host "$Cyan$Bold║             Next-Gen Windows AI & Voice Automation                   ║$Reset"
Write-Host "$Cyan$Bold╚══════════════════════════════════════════════════════════════════════╝$Reset"
Write-Host ""

# 1. Detect Python executable
$PythonExe = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $PythonExe = ".\.venv\Scripts\python.exe"
    Write-Host "$Green✔$Reset Using virtual environment: $Dim.venv$Reset"
} else {
    Write-Host "$Yellow⚠$Reset Virtual environment (.venv) not found. Falling back to system python."
}

# 2. Ensure Ollama Service in WSL
$OllamaHost = "http://127.0.0.1:11434"
$OllamaOnline = $false

try {
    $resp = Invoke-RestMethod -Uri "$OllamaHost/api/tags" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($resp) {
        $OllamaOnline = $true
        Write-Host "$Green✔$Reset WSL Ollama service is online at $Dim$OllamaHost$Reset"
    }
} catch {
    $OllamaOnline = $false
}

if (-not $OllamaOnline) {
    Write-Host "$Yellow⚡$Reset Ollama service not detected. Attempting automatic start in WSL..."
    try {
        Start-Process wsl -ArgumentList "-d Ubuntu-24.04 bash -c 'OLLAMA_HOST=0.0.0.0:11434 nohup /usr/local/bin/ollama serve > /tmp/ollama.log 2>&1 &'" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        $resp = Invoke-RestMethod -Uri "$OllamaHost/api/tags" -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($resp) {
            $OllamaOnline = $true
            Write-Host "$Green✔$Reset WSL Ollama daemon started successfully."
        }
    } catch {
        Write-Host "$Yellow⚠$Reset Could not auto-start Ollama in WSL. Operating in deterministic Fast-Path NLP mode."
    }
}

# 3. Launch JARVIS Main Application
Write-Host "$Green⚡$Reset Starting JARVIS Agent Core...`n"
& $PythonExe -m app.main $args
