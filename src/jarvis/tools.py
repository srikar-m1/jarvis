from __future__ import annotations

import platform
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        if not name or name in self._tools:
            raise ValueError(f"Tool '{name}' is invalid or already registered.")
        self._tools[name] = handler

    def run(self, name: str, *args: Any, **kwargs: Any) -> Any:
        try:
            handler = self._tools[name]
        except KeyError as exc:
            raise ValueError(f"Tool '{name}' is not allowlisted.") from exc
        return handler(*args, **kwargs)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


def system_status(path: str | Path = ".") -> dict[str, str | int]:
    usage = shutil.disk_usage(Path(path).resolve())
    return {
        "platform": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "processor": platform.machine(),
        "disk_free_gb": round(usage.free / (1024**3), 2),
        "executable": sys.executable,
    }


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("system_status", system_status)
    return registry
