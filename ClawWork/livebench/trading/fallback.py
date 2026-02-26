from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TradeDecision:
    action: str  # BUY / SELL / HOLD / NO_TRADE
    reason: str
    metadata: dict[str, Any]


def no_trade(reason: str, **metadata: Any) -> TradeDecision:
    return TradeDecision(action="NO_TRADE", reason=reason, metadata=metadata)
