from dataclasses import dataclass
from typing import Any

from livebench.audit.audit_logger import AuditLogger
from livebench.configs.feature_flags import FeatureFlags
from livebench.trading.fallback import TradeDecision, no_trade
from livebench.trading.kill_switch import KillSwitch


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    decision: TradeDecision | None


def guard_trade_request(
    *,
    symbol: str,
    flags: FeatureFlags,
    kill_switch: KillSwitch,
    audit: AuditLogger,
    context: dict[str, Any] | None = None,
) -> GuardrailResult:
    ctx = context or {}

    if kill_switch.is_enabled():
        decision = no_trade("Global kill switch enabled", symbol=symbol, **ctx)
        audit.event("trade_blocked", symbol=symbol, reason="kill_switch", context=ctx)
        return GuardrailResult(allowed=False, decision=decision)

    if not flags.trading_enabled:
        decision = no_trade("Trading disabled by feature flag", symbol=symbol, **ctx)
        audit.event("trade_blocked", symbol=symbol, reason="trading_disabled", context=ctx)
        return GuardrailResult(allowed=False, decision=decision)

    audit.event("trade_guardrails_passed", symbol=symbol, paper_mode=flags.paper_mode, context=ctx)
    return GuardrailResult(allowed=True, decision=None)
