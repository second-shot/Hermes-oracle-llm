from __future__ import annotations

from pathlib import Path

from hermes_growth.contracts import Reflection
from hermes_growth.skill_registry import default_growth_root
from hermes_growth.storage import append_jsonl, read_jsonl


class ReflectionStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_growth_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "reflections.jsonl"

    def append(self, reflection: Reflection) -> None:
        errors = reflection.validate()
        if errors:
            raise ValueError("; ".join(errors))
        append_jsonl(self.path, reflection.to_dict())

    def reflections(self) -> list[Reflection]:
        return [
            Reflection.from_dict(value)
            for value in read_jsonl(self.path)
        ]
