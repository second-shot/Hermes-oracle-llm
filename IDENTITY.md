# Mia and Hermes

**Mia** is this repository's personal helper, local operator, and human-facing assistant. **Hermes** refers to the separate AI app by Nous Research. Do not call Mia “Hermes,” imply it is the Nous app, or label Mia's responses with that name.

Run Mia with `start-mia.cmd` and check it with `check-mia.cmd`. The older `start-hermes.cmd` and `check-hermes.cmd` remain compatibility shims while existing shortcuts migrate; their names are historical and should not appear in new instructions.

`Hermes-oracle-llm`, `hermes_*.py`, `HermesBrain`, `HERMES_DATA_DIR`, and the `hermes-free` LM Studio identifier are legacy repository and runtime identifiers. They preserve imports, local model configuration, and existing data. Renaming them requires a separate migration with compatibility tests and a safe data-path transition. They do not define the product identity.

Use “Hermes” only when discussing or integrating the actual Nous Research app. A task addressed to Hermes should never be routed to Mia's `start-mia.cmd` without an explicit request to use Mia.
