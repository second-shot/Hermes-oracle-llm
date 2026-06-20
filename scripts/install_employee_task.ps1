$Repo = "C:\Users\max\Hermes-oracle-llm"
Set-Location -LiteralPath $Repo
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { throw "Python not found. Install Python or add it to PATH first." }
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Repo\hermes_employee.py`" tick"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Trigger.Repetition = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)
Register-ScheduledTask -TaskName "HermesMIAEmployeeTick" -Action $Action -Trigger $Trigger -Description "Run MIA tick every 15 minutes while logged in" -Force
Write-Host "Installed HermesMIAEmployeeTick. It runs a visible safe tick command, not a hidden daemon."
