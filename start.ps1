$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'Creating Python virtual environment…' -ForegroundColor Cyan
    python -m venv .venv
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Write-Host 'Checking Python dependencies…' -ForegroundColor Cyan
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }

$providerLine = Get-Content '.env' | Where-Object { $_ -match '^AI_PROVIDER=' } | Select-Object -First 1
$provider = if ($env:AI_PROVIDER) { $env:AI_PROVIDER } elseif ($providerLine) { $providerLine.Substring('AI_PROVIDER='.Length).Trim().Trim('"').Trim("'") } else { 'ollama' }
if ($provider -eq 'ollama') {
$ollamaPath = $null
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCommand) { $ollamaPath = $ollamaCommand.Source }
if (-not $ollamaPath) {
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $candidate) { $ollamaPath = $candidate }
}
if ($ollamaPath) {
    try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null }
    catch {
        Write-Host 'Starting local Ollama service…' -ForegroundColor Cyan
        Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; break } catch { }
        }
    }
    try {
        $envFile = Get-Content '.env'
        $modelLine = $envFile | Where-Object { $_ -match '^OLLAMA_MODEL=' } | Select-Object -First 1
        $model = if ($modelLine) { $modelLine.Substring('OLLAMA_MODEL='.Length) } else { 'qwen2.5-coder:3b' }
        $models = (Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3).models.name
        if ($models -notcontains $model) { Write-Warning "Ollama is running but '$model' is not installed. Run: ollama pull $model" }
    } catch { Write-Warning 'Ollama is not reachable. The app will start in its visible offline fallback mode.' }
} else {
    Write-Warning 'Ollama is not installed/on PATH. Install Ollama and pull qwen2.5-coder:3b to enable local AI; fallback mode is available meanwhile.'
}
} else {
    Write-Host "Using configured provider: $provider. The dashboard will report its connection status." -ForegroundColor Cyan
}

$port = 8010
while (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { $port++ }
Write-Host "Starting Coder Buddy at http://127.0.0.1:$port …" -ForegroundColor Green
$server = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$port") -WorkingDirectory $PSScriptRoot -PassThru
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { }
}
if (-not $ready) { throw "Server process $($server.Id) did not become ready. Check its console output." }
Start-Process "http://127.0.0.1:$port"
Write-Host "Coder Buddy is ready. Close its server window or stop PID $($server.Id) when finished." -ForegroundColor Green
