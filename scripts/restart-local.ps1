$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment Python not found at: $venvPython"
}

Write-Host 'Stopping existing local services...' -ForegroundColor Cyan

$streamlitPy = Get-CimInstance Win32_Process | Where-Object { $_.Name -ieq 'python.exe' -and $_.CommandLine -match 'streamlit_app.py' }
if ($streamlitPy) { $streamlitPy | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }

$func = Get-Process -Name func -ErrorAction SilentlyContinue
if ($func) { $func | Stop-Process -Force }

$azNode = Get-CimInstance Win32_Process | Where-Object { $_.Name -ieq 'node.exe' -and $_.CommandLine -match 'azurite' }
if ($azNode) { $azNode | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }

Start-Sleep -Seconds 1

Write-Host 'Starting Azurite, Functions, and Streamlit in separate terminals...' -ForegroundColor Cyan

$azuriteCommand = "Set-Location '$projectRoot'; azurite --location .azurite --debug .azurite\\debug.log"
$funcCommand = "Set-Location '$projectRoot'; func start"
$streamlitCommand = "Set-Location '$projectRoot'; & '$venvPython' -m streamlit run streamlit_app.py --server.headless true"

Start-Process powershell -ArgumentList @('-NoExit', '-Command', $azuriteCommand) | Out-Null
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $funcCommand) | Out-Null
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $streamlitCommand) | Out-Null

Write-Host 'Waiting for services to listen on expected ports...' -ForegroundColor Cyan

$expectedPorts = @(10000, 7071, 8501)
$deadline = (Get-Date).AddSeconds(30)

while ((Get-Date) -lt $deadline) {
    $listening = $expectedPorts | Where-Object {
        Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
    }

    if ($listening.Count -eq $expectedPorts.Count) {
        break
    }

    Start-Sleep -Seconds 1
}

Write-Host ''
Write-Host 'Service Port Status:' -ForegroundColor Green
foreach ($port in $expectedPorts) {
    $isListening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($isListening) {
        Write-Host "  Port $port LISTEN" -ForegroundColor Green
    }
    else {
        Write-Host "  Port $port NOT_LISTENING" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host 'Done. Check opened terminal windows for live logs.' -ForegroundColor Cyan
