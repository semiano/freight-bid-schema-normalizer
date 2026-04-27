# Startup Procedure (Local Development)

Use this procedure to quickly bring up all required local services in a clean, repeatable way.

## Goal

Start these services in separate terminal sessions:
- Azurite storage emulator
- Azure Functions host (`func start`)
- Streamlit UI (`streamlit_app.py`)

## Prerequisites

- Workspace opened at project root.
- Virtual environment exists at `.venv`.
- Azure Functions Core Tools installed (`func`).
- Azurite installed (`azurite`).

## 1) Clean Stop (run once in a PowerShell terminal)

```powershell
$streamlitPy = Get-CimInstance Win32_Process | Where-Object { $_.Name -ieq 'python.exe' -and $_.CommandLine -match 'streamlit_app.py' }
if ($streamlitPy) { $streamlitPy | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }

$func = Get-Process -Name func -ErrorAction SilentlyContinue
if ($func) { $func | Stop-Process -Force }

$azNode = Get-CimInstance Win32_Process | Where-Object { $_.Name -ieq 'node.exe' -and $_.CommandLine -match 'azurite' }
if ($azNode) { $azNode | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }

Write-Output 'Stopped Streamlit/func/Azurite processes.'
```

## 2) Start Services (separate terminals)

Open 3 separate terminals from the project root.

### Terminal A: Azurite

```powershell
azurite --location .azurite --debug .azurite\debug.log
```

### Terminal B: Azure Functions host

```powershell
func start
```

### Terminal C: Streamlit (via venv Python)

```powershell
& "c:/Users/stephenmiano/RXO document normalizer/.venv/Scripts/python.exe" -m streamlit run streamlit_app.py --server.headless true
```

Notes:
- Use the venv Python path for Streamlit to avoid PATH issues.
- Keep each service in its own terminal so logs remain visible and isolated.

## 3) Health Check (run in any PowerShell terminal)

```powershell
$ports = @(10000,7071,8501)
foreach ($p in $ports) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($c) { Write-Output ("Port " + $p + " LISTEN") }
  else { Write-Output ("Port " + $p + " NOT_LISTENING") }
}
```

Expected:
- `Port 10000 LISTEN` (Azurite Blob)
- `Port 7071 LISTEN` (Functions)
- `Port 8501 LISTEN` (Streamlit)

## 4) Quick Troubleshooting

- If `streamlit` is not recognized, always launch via:
  - `& "c:/Users/stephenmiano/RXO document normalizer/.venv/Scripts/python.exe" -m streamlit ...`
- If Functions cannot connect to blob storage (`127.0.0.1:10000` refused), restart Azurite first, then restart `func start`.
- If you see Azurite API version errors (for example, unsupported `2026-02-06`), set an override before startup:
  - `$env:AZURE_BLOB_API_VERSION = "2021-12-02"`
- If a port is occupied unexpectedly, run Step 1 (Clean Stop) and start again in the order: Azurite -> Functions -> Streamlit.

## Recommended Bring-Up Order

1. Clean stop
2. Azurite
3. Functions host
4. Streamlit
5. Port health check

## One-Command Option

You can also run:

```powershell
.\scripts\restart-local.ps1
```

This script performs clean stop, starts each service in separate PowerShell windows, and prints port status for `10000`, `7071`, and `8501`.
