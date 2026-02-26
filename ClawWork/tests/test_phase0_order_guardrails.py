from livebench.tools.direct_tools import fyers_place_order


def test_fyers_place_order_blocked_when_trading_disabled(monkeypatch):
    monkeypatch.delenv("TRADING_ENABLED", raising=False)
    monkeypatch.delenv("GLOBAL_KILL_SWITCH", raising=False)

    result = fyers_place_order.invoke(
        {"order_payload": {"symbol": "NSE:SBIN-EQ", "qty": 1}}
    )

    assert result["success"] is True
    assert result["blocked"] is True
    assert result["order_sent"] is False
    assert result["guardrail"]["reason"] == "Trading disabled by feature flag"


def test_fyers_place_order_blocked_when_kill_switch_enabled(monkeypatch):
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("GLOBAL_KILL_SWITCH", "true")

    result = fyers_place_order.invoke(
        {"order_payload": {"symbol": "NSE:TCS-EQ", "qty": 1}}
    )

    assert result["success"] is True
    assert result["blocked"] is True
    assert result["order_sent"] is False
    assert result["guardrail"]["reason"] == "Global kill switch enabled"


def test_fyers_place_order_reaches_dry_run_when_guardrails_pass(monkeypatch):
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.delenv("GLOBAL_KILL_SWITCH", raising=False)
    monkeypatch.setenv("FYERS_DRY_RUN", "true")
    monkeypatch.delenv("FYERS_ALLOW_LIVE_ORDERS", raising=False)

    result = fyers_place_order.invoke(
        {"order_payload": {"symbol": "NSE:RELIANCE-EQ", "qty": 1}}
    )

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["order_sent"] is False
    assert result["reason"] == "Live order blocked by safety settings"
