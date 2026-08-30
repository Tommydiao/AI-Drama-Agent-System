$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot 'apps\api'
$webRoot = Join-Path $repoRoot 'apps\web'
$python = Join-Path $apiRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
  throw "Python environment missing. Run: python -m venv apps/api/.venv; apps/api/.venv/Scripts/python.exe -m pip install -e 'apps/api[dev]'"
}
$apiProcess = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $apiRoot -WindowStyle Hidden -PassThru
$webProcess = Start-Process -FilePath 'pnpm.cmd' -ArgumentList 'dev','--hostname','127.0.0.1' -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru
$health = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  try { if ((Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health').StatusCode -eq 200) { $health = $true; break } } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $health) { throw "FastAPI did not become healthy (pid $($apiProcess.Id))." }
Write-Output "AI Drama Agent is running: http://127.0.0.1:3000"
Write-Output "FastAPI pid: $($apiProcess.Id); Next.js pid: $($webProcess.Id)"
Start-Process 'http://127.0.0.1:3000'

