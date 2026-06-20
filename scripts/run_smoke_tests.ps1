param(
    [string]$Repo = "."
)

$ErrorActionPreference = "Stop"
$RepoPath = Resolve-Path -LiteralPath $Repo
Set-Location -LiteralPath $RepoPath

python -m compileall -q hermes_employee.py
python .\scripts\validate_mia_package.py .
python hermes_employee.py status
python hermes_employee.py character
python hermes_employee.py rights
python hermes_employee.py skills
python hermes_employee.py sources
python hermes_employee.py security
python hermes_employee.py ethical-check "scan my own repo for leaked keys"
python hermes_employee.py ethical-check "steal someone's password"
python hermes_employee.py source-plan "What local sources should MIA trust first?"
python hermes_employee.py security-check

Write-Host "MIA smoke tests completed. Review generated security reports and git status."
