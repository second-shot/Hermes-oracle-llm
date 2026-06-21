param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8787"
)

$ErrorActionPreference = "Stop"

function Invoke-OracleJson {
    param(
        [string]$Url,
        [string]$Method = "GET",
        [hashtable]$Body = $null
    )

    if ($null -eq $Body) {
        return Invoke-RestMethod -Uri $Url -Method $Method -ContentType "application/json"
    }

    return Invoke-RestMethod -Uri $Url -Method $Method -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

Write-Host "Oracle V1 smoke test starting against $ApiBaseUrl"

$Health = Invoke-OracleJson -Url "$ApiBaseUrl/api/health"
if ($Health.status -ne "ok") { throw "Health check failed." }

$Intake = Invoke-OracleJson -Url "$ApiBaseUrl/api/oracle/intake" -Method "POST" -Body @{
    mode = "architect"
    objective = "Turn an unstructured local request into a safe execution plan"
    text = "Delete old production logs and deploy the new plan after review"
    task = "Prepare the next local operator checkpoint"
    metadata = @{ source = "smoke-script" }
}

$ConfirmationId = $Intake.data.confirmation.id
if (-not $ConfirmationId) { throw "Expected a confirmation request from the risky smoke intake." }

$Approved = Invoke-OracleJson -Url "$ApiBaseUrl/api/confirmations/$ConfirmationId/approve" -Method "POST" -Body @{
    decisionNote = "Smoke approved"
}

$State = Invoke-OracleJson -Url "$ApiBaseUrl/api/oracle/state"
$Notifications = Invoke-OracleJson -Url "$ApiBaseUrl/api/notifications"
$Memory = Invoke-OracleJson -Url "$ApiBaseUrl/api/memory"
$Logs = Invoke-OracleJson -Url "$ApiBaseUrl/api/logs"

Write-Host "Smoke complete."
Write-Host "Visual state: $($State.data.visualState)"
Write-Host "Notification count: $($Notifications.data.items.Count)"
Write-Host "Memory entries: $($Memory.data.structured.oracle_v1.entries.Count)"
Write-Host "Log entries: $($Logs.data.entries.Count)"
