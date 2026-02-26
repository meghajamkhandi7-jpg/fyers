import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FeatureFlags:
    trading_enabled: bool = False
    paper_mode: bool = True
    learning_enabled: bool = True

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        return cls(
            trading_enabled=_to_bool(os.getenv("TRADING_ENABLED"), False),
            paper_mode=_to_bool(os.getenv("PAPER_MODE"), True),
            learning_enabled=_to_bool(os.getenv("LEARNING_ENABLED"), True),
        )
