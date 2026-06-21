from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .store import OracleStore


class StorageAdapter(Protocol):
    def get_store(self) -> OracleStore:
        ...


class AuthAdapter(Protocol):
    def current_operator(self) -> str:
        ...


class RealtimeAdapter(Protocol):
    def publish(self, topic: str, payload: dict) -> None:
        ...


class LocalStorageAdapter:
    def __init__(self, data_root: Path):
        self._store = OracleStore(data_root)

    def get_store(self) -> OracleStore:
        return self._store


class LocalAuthAdapter:
    def current_operator(self) -> str:
        return "local-operator"


class NoopRealtimeAdapter:
    def publish(self, topic: str, payload: dict) -> None:
        return None

