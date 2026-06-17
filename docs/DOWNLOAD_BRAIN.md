# Hermes V5 — Download Brain

Hermes V5 turns the local Downloads folder into an intake pipeline.

## Purpose

Every file entering the machine becomes structured signal instead of dead clutter.
The pipeline is deterministic, local-first, and standard-library only.

## What V5 does

- Scans the Downloads directory.
- Ignores folders and symlinks.
- Collects safe filesystem metadata.
- Classifies files into documents, images, videos, audio, archives, code, spreadsheets or unknown.
- Routes files into Hermes project domains.
- Maintains a persistent processing queue.
- Writes a manifest for review.
- Suggests next actions without moving or deleting user files.

## Commands

```bash
python main.py download scan
python main.py download status
python main.py download queue
python main.py download queue new
```

Optional custom directory:

```bash
python main.py download scan ~/Downloads
```

Environment override:

```bash
HERMES_DOWNLOADS_DIR=/path/to/folder python main.py download scan
```

## Output files

```text
memory/downloads_queue.json
memory/downloads_manifest.json
```

## Project routing

| Project | Examples |
|---|---|
| personal | passport, bank, DWP, UC, identity |
| vehicle | Mini, MOT, insurance, mechanic |
| resale | gold, silver, watch, Vinted, eBay, inventory |
| hermes | Hermes, Oracle, MIA, model, Qwen, MLX |
| creative | music, video, visual, art, audio |
| community | housing, Hackney, legal, collective |

## Safety

V5 does not delete files.
V5 does not move files.
V5 does not upload files.
V5 does not call an LLM.
V5 does not use network access.

It only scans, classifies, queues, and reports.

## Next evolution

V5.1 should add opt-in extraction:

- OCR for images and PDFs.
- SmolVLM vision tagging.
- Duplicate detection.
- Operator handoff for resale files.
- Identity-memory handoff for personal documents.
