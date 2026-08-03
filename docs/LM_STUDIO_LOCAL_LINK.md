# LM Studio Local Link

Hermes uses LM Studio locally before any cloud provider. Its expected server URL is `http://127.0.0.1:1234/v1`.

## Start the local server

1. Open LM Studio.
2. Download or select a local model and load it.
3. Open LM Studio's Developer/Local Server view.
4. Set the port to `1234` and start the server.
5. Confirm the server shows `http://127.0.0.1:1234` (Hermes appends the OpenAI-compatible `/v1` path through its configured base URL).

## Test the link

From the repository root, run:

```powershell
python scripts/check_lm_studio.py
python hermes_employee.py provider
```

The health check prints `ONLINE` when `GET /v1/models` responds. If it prints `OFFLINE`, open LM Studio, load a model, start the local server, and confirm port `1234`.

Hermes must use local LM Studio before any cloud fallback. Local mode does not fall back to OpenAI when LM Studio is offline.

OpenAI API and cloud MCP services can use paid credits and are not used in local mode. Keep `HERMES_CLOUD_ENABLED=false`; no OpenAI key is required.
