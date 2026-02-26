import pytest

from livebench.tools.direct_tools import institutional_desk_decide
from livebench.trading.institutional_desk import run_institutional_desk


def _base_payload():
    return {
        "analysts": [
            {
                "role": "technical",
                "stance": "BULLISH",
                "confidence": "HIGH",
                "rationale": "Momentum breakout above key level.",
                "evidence": ["RSI>60", "20EMA cross"]
            },
            {
                "role": "fundamental",
                "stance": "BULLISH",
                "confidence": "MEDIUM",
                "rationale": "Earnings quality improving.",
                "evidence": ["Revenue growth", "Margin expansion"]
            },
            {
                "role": "sentiment",
                "stance": "NEUTRAL",
                "confidence": "LOW",
                "rationale": "Headline flow mixed.",
                "evidence": ["Neutral social sentiment"]
            },
        ],
        "trader_proposal": {
            "action": "BUY_CALL",
            "symbol": "NSE:RELIANCE-EQ",
            "quantity": 1,
            "confidence": "MEDIUM",
            "rationale": "Aligned with analyst majority and risk budget.",
            "risk_budget_pct": 1.5,
        },
        "risk_review": {
            "approved": True,
            "reason": "All risk checks passed.",
            "hard_blocks": [],
            "max_position_pct": 2.0,
        },
    }


def test_phase1_consensus_approved_buy_call():
    decision = run_institutional_desk(_base_payload())

    assert decision["approved"] is True
    assert decision["action"] == "BUY_CALL"
    assert decision["quantity"] == 1
    assert decision["schema_version"] == "phase1.v1"


def test_phase1_risk_veto_forces_no_trade():
    payload = _base_payload()
    payload["risk_review"]["approved"] = False
    payload["risk_review"]["reason"] = "Daily loss limit breached"
    payload["risk_review"]["hard_blocks"] = ["daily_loss_cap"]

    decision = run_institutional_desk(payload)

    assert decision["approved"] is False
    assert decision["action"] == "NO_TRADE"
    assert "Risk manager veto" in decision["rationale"]


def test_phase1_trader_misalignment_forces_no_trade():
    payload = _base_payload()
    payload["trader_proposal"]["action"] = "BUY_PUT"

    decision = run_institutional_desk(payload)

    assert decision["approved"] is False
    assert decision["action"] == "NO_TRADE"
    assert "misaligned" in decision["rationale"].lower()


def test_phase1_schema_validation_error():
    payload = _base_payload()
    del payload["trader_proposal"]["symbol"]

    with pytest.raises(ValueError):
        run_institutional_desk(payload)


def test_phase1_tool_wrapper_success_path():
    result = institutional_desk_decide.invoke({"payload": _base_payload()})

    assert result["success"] is True
    assert result["decision"]["action"] == "BUY_CALL"


def test_phase1_tool_wrapper_validation_error():
    bad_payload = _base_payload()
    bad_payload["analysts"] = [{"role": "technical"}]

    result = institutional_desk_decide.invoke({"payload": bad_payload})

    assert result["success"] is False
    assert "required" in result["error"].lower() or "must" in result["error"].lower()
