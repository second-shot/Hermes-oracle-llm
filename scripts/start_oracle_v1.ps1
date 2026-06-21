$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

python -m oracle_v1.http_api --host 127.0.0.1 --port 8787 --data-root $RepoRoot
