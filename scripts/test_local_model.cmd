@echo off
curl http://localhost:1234/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"local-model\",\"messages\":[{\"role\":\"user\",\"content\":\"Say Hermes local runtime is alive in one sentence.\"}],\"temperature\":0.2}"
