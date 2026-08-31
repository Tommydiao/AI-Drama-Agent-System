$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot 'apps\api'
$python = Join-Path $apiRoot '.venv\Scripts\python.exe'

if (-not $env:TEST_DATABASE_URL) {
  throw 'TEST_DATABASE_URL must point to a disposable PostgreSQL integration database.'
}
if (-not $env:TEST_DATABASE_URL.StartsWith('postgresql')) {
  throw 'TEST_DATABASE_URL must use PostgreSQL.'
}

$previousDatabaseUrl = $env:DRAMA_DATABASE_URL
try {
  $env:DRAMA_DATABASE_URL = $env:TEST_DATABASE_URL
  & $python -m alembic -c (Join-Path $apiRoot 'alembic.ini') upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Alembic upgrade failed.' }
  & $python -m pytest -q (Join-Path $apiRoot 'tests\test_postgres_integration.py')
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL integration tests failed.' }
}
finally {
  $env:DRAMA_DATABASE_URL = $previousDatabaseUrl
}
