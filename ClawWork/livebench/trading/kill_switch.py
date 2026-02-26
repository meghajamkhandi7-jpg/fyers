import os
import threading


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class KillSwitch:
    """
    GLOBAL_KILL_SWITCH env controls startup state.
    Runtime toggle is thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = _to_bool(os.getenv("GLOBAL_KILL_SWITCH"), False)

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
