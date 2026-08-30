"""
Memory-Augmented Graph (MAG) Store.
JSON-based persistent facts and user preferences.
"""

import json
import threading
from pathlib import Path
from typing import Any, Optional

from config.logger import get_logger
from config.settings import settings

logger = get_logger("memory.mag")

MAG_FILE = settings.data_dir / "mag_facts.json"


class MAGStore:
    """Persistent key-value store for user facts and preferences."""

    def __init__(self):
        self._facts: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if MAG_FILE.exists():
            try:
                self._facts = json.loads(MAG_FILE.read_text(encoding="utf-8"))
                logger.info("Loaded %d facts from MAG store", len(self._facts))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load MAG store: %s", e)
                self._facts = {}

    def _save(self) -> None:
        try:
            MAG_FILE.write_text(
                json.dumps(self._facts, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to save MAG store: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._facts.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._facts[key] = value
            self._save()

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._facts:
                del self._facts[key]
                self._save()
                return True
            return False

    def query(self, prefix: str) -> dict[str, Any]:
        with self._lock:
            return {k: v for k, v in self._facts.items() if k.startswith(prefix)}

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._facts)

    def clear(self) -> None:
        with self._lock:
            self._facts.clear()
            self._save()


mag_store = MAGStore()
