# Hermes free-only model rotation

Hermes always tries local runtimes first:

1. LM Studio on Windows
2. llama.cpp server
3. MLX on Apple silicon
4. an explicitly enabled, verified zero-cost OpenAI-compatible endpoint

Hermes never auto-selects a paid, trial-credit, or unknown-cost endpoint.

## Default local-only mode

No remote settings are required. Start Hermes with:

```bat
cd /d C:\Users\max\Hermes-oracle-llm
git switch main
git pull --ff-only origin main
start-hermes.cmd
```

Check the active local model and runtime:

```bat
check-hermes.cmd
```

## Optional verified free remote fallback

This fallback is disabled unless every required variable is set. The operator must independently verify that the chosen provider and model are currently zero-cost.

```bat
set HERMES_ENABLE_FREE_REMOTE=1
set HERMES_FREE_REMOTE_VERIFIED_ZERO_COST=1
set HERMES_FREE_REMOTE_BASE_URL=https://PROVIDER.example/v1
set HERMES_FREE_REMOTE_MODEL=provider/free-model-id
set HERMES_FREE_REMOTE_PROVIDER=free_remote
set HERMES_FREE_REMOTE_TOKEN_ENV=HERMES_FREE_REMOTE_API_KEY
set HERMES_FREE_REMOTE_API_KEY=REDACTED_TOKEN
start-hermes.cmd
```

Rules enforced in code:

- the endpoint must use HTTPS;
- the endpoint must be explicitly enabled;
- the operator must explicitly mark it verified zero-cost;
- the provider record is locked to `cost: free` and `free_model_only: true`;
- local providers are always attempted first;
- a failed free request does not unlock any paid provider;
- secrets stay in environment variables and are not written to source control.

## Disable remote fallback

```bat
set HERMES_ENABLE_FREE_REMOTE=
set HERMES_FREE_REMOTE_VERIFIED_ZERO_COST=
set HERMES_FREE_REMOTE_BASE_URL=
set HERMES_FREE_REMOTE_MODEL=
set HERMES_FREE_REMOTE_PROVIDER=
set HERMES_FREE_REMOTE_TOKEN_ENV=
set HERMES_FREE_REMOTE_API_KEY=
```

Restart Hermes after clearing the variables.

## Verify

```bat
python -m pytest -q tests/test_free_remote_fallback.py tests/test_hermes_local_first.py
python scripts/hermes_doctor.py
```

Expected routing result values:

- `local`: a local model answered;
- `free-remote`: the explicitly enabled verified free endpoint answered;
- `fallback_status: disabled`: remote fallback was not enabled;
- `fallback_status: request failed`: the free endpoint failed and Hermes stopped without switching to paid usage.

## Roll back this branch

```bat
cd /d C:\Users\max\Hermes-oracle-llm
git switch main
git branch -D agent/yesterday-free-router-integration
```
