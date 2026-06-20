$ErrorActionPreference = "Continue"

Write-Host "=== MIA CLI v2 smoke tests ==="

python hermes_employee.py status
python hermes_employee.py character
python hermes_employee.py rights
python hermes_employee.py skills
python hermes_employee.py sources
python hermes_employee.py security
python hermes_employee.py ethical-check "status check local runtime"
python hermes_employee.py source-plan "build next local bridge without paid APIs"
python hermes_employee.py security-check "build next local bridge without paid APIs"
python hermes_employee.py decide "build next Hermes local bridge without paid APIs"
python hermes_employee.py tick "status check local runtime"
python hermes_employee.py validate

Write-Host "MIA CLI v2 smoke tests completed."
