python hermes_model_router.py status
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python hermes_model_router.py route "Compress this task and choose a local model."
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python hermes_model_router.py test
exit $LASTEXITCODE
