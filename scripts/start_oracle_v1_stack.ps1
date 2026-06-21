$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendCandidates = @(
    $env:ORACLE_WEB_ROOT,
    (Join-Path $RepoRoot "G0DM0D3"),
    (Join-Path $HOME ".config\superpowers\worktrees\G0DM0D3\oracle-v1-fusion")
) | Where-Object { $_ }

$FrontendRoot = $null
foreach ($Candidate in $FrontendCandidates) {
    if (Test-Path (Join-Path $Candidate "package.json")) {
        $FrontendRoot = $Candidate
        break
    }
}

if (-not $FrontendRoot) {
    throw "Could not locate the G0DM0D3 frontend repo. Set ORACLE_WEB_ROOT or ensure G0DM0D3\package.json exists."
}

$PythonArgs = "-m oracle_v1.http_api --host 127.0.0.1 --port 8787 --data-root `"$RepoRoot`""
$NodeArgs = "/c npm run dev -- --hostname 127.0.0.1 --port 3000"

Start-Process -FilePath "python" -ArgumentList $PythonArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden
Start-Sleep -Seconds 2
Start-Process -FilePath "cmd.exe" -ArgumentList $NodeArgs -WorkingDirectory $FrontendRoot -WindowStyle Hidden
Start-Sleep -Seconds 4
Start-Process "http://127.0.0.1:3000"

Write-Host "Oracle V1 stack launch requested."
Write-Host "Backend:  http://127.0.0.1:8787"
Write-Host "Frontend: http://127.0.0.1:3000"
Write-Host "Frontend repo: $FrontendRoot"
