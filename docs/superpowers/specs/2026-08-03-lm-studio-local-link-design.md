# LM Studio Local Link Design

Hermes uses LM Studio's OpenAI-compatible server at `http://127.0.0.1:1234/v1` as its default model provider. A checked-in JSON file persists provider policy, while environment variables may override the base URL without storing secrets.

`hermes_provider.py` is the policy boundary. It loads config, accepts loopback URLs, rejects remote and OpenAI cloud URLs unless their explicit policy gates permit them, and performs a standard-library-only `/models` health check. The standalone Python and PowerShell checks call the same resolver so CLI and application behavior cannot drift.

`hermes_employee.py provider` prints the resolved provider, base URL, local-only state, health, and cloud setting. `hermes_refraction.py test` provides a local-only compatibility check. Offline LM Studio is an expected operational state and is reported without cloud fallback.

Tests cover loopback classification, default resolution, unsafe override rejection, offline health behavior, and CLI status output. No real `.env`, credential, cloud request, deletion, or push is part of this change.
