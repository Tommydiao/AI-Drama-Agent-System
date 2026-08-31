$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot 'apps\api'
$python = Join-Path $apiRoot '.venv\Scripts\python.exe'

if (-not $env:TEMPORAL_TARGET) { $env:TEMPORAL_TARGET = '127.0.0.1:7233' }
if (-not $env:TEMPORAL_NAMESPACE) { $env:TEMPORAL_NAMESPACE = 'default' }
if (-not $env:TEMPORAL_TASK_QUEUE) { $env:TEMPORAL_TASK_QUEUE = 'ai-drama-projects' }

Push-Location $apiRoot
try {
  & $python -m app.temporal_worker
}
finally {
  Pop-Location
}
