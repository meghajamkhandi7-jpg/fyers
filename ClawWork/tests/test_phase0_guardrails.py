from livebench.audit.audit_logger import AuditLogger
from livebench.configs.feature_flags import FeatureFlags
from livebench.trading.guardrails import guard_trade_request
from livebench.trading.kill_switch import KillSwitch


def test_feature_flags_defaults(monkeypatch):
    monkeypatch.delenv("TRADING_ENABLED", raising=False)
    monkeypatch.delenv("PAPER_MODE", raising=False)
    monkeypatch.delenv("LEARNING_ENABLED", raising=False)

    flags = FeatureFlags.from_env()
    assert flags.trading_enabled is False
    assert flags.paper_mode is True
    assert flags.learning_enabled is True


def test_feature_flags_from_env(monkeypatch):
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_MODE", "false")
    monkeypatch.setenv("LEARNING_ENABLED", "1")

    flags = FeatureFlags.from_env()
    assert flags.trading_enabled is True
    assert flags.paper_mode is False
    assert flags.learning_enabled is True


def test_kill_switch_runtime_toggle(monkeypatch):
    monkeypatch.delenv("GLOBAL_KILL_SWITCH", raising=False)
    ks = KillSwitch()
    assert ks.is_enabled() is False
    ks.enable()
    assert ks.is_enabled() is True
    ks.disable()
    assert ks.is_enabled() is False


def test_guardrail_blocks_when_trading_disabled(monkeypatch):
    monkeypatch.delenv("GLOBAL_KILL_SWITCH", raising=False)
    flags = FeatureFlags(trading_enabled=False, paper_mode=True, learning_enabled=True)
    ks = KillSwitch()
    audit = AuditLogger("test.audit")

    result = guard_trade_request(
        symbol="AAPL",
        flags=flags,
        kill_switch=ks,
        audit=audit,
        context={"source": "unit_test"},
    )
    assert result.allowed is False
    assert result.decision is not None
    assert result.decision.action == "NO_TRADE"


def test_guardrail_blocks_when_kill_switch_enabled(monkeypatch):
    monkeypatch.setenv("GLOBAL_KILL_SWITCH", "true")
    flags = FeatureFlags(trading_enabled=True, paper_mode=True, learning_enabled=True)
    ks = KillSwitch()
    audit = AuditLogger("test.audit")

    result = guard_trade_request(symbol="AAPL", flags=flags, kill_switch=ks, audit=audit)
    assert result.allowed is False
    assert result.decision is not None
    assert result.decision.reason == "Global kill switch enabled"


def test_guardrail_allows_when_all_clear(monkeypatch):
    monkeypatch.delenv("GLOBAL_KILL_SWITCH", raising=False)
    flags = FeatureFlags(trading_enabled=True, paper_mode=True, learning_enabled=True)
    ks = KillSwitch()
    audit = AuditLogger("test.audit")

    result = guard_trade_request(symbol="AAPL", flags=flags, kill_switch=ks, audit=audit)
    assert result.allowed is True
    assert result.decision is None
