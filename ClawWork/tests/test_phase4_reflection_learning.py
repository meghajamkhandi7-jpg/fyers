from pathlib import Path

from livebench.tools.direct_tools import (
    institutional_desk_decide,
    institutional_record_outcome,
    set_global_state,
)
from livebench.trading.experience_store import ExperienceStore


def _base_payload():
    return {
        "analysts": [
            {
                "role": "technical",
                "stance": "BULLISH",
                "confidence": "HIGH",
                "rationale": "Uptrend continuation.",
                "evidence": ["EMA trend", "Volume support"],
            },
            {
                "role": "fundamental",
                "stance": "BULLISH",
                "confidence": "MEDIUM",
                "rationale": "Business momentum stable.",
                "evidence": ["Revenue growth"],
            },
            {
                "role": "sentiment",
                "stance": "NEUTRAL",
                "confidence": "LOW",
                "rationale": "Mixed macro cues.",
                "evidence": ["Neutral sentiment"],
            },
        ],
        "trader_proposal": {
            "action": "BUY_CALL",
            "symbol": "NSE:ITC-EQ",
            "quantity": 1,
            "confidence": "MEDIUM",
            "rationale": "Desk consensus alignment.",
            "risk_budget_pct": 0.4,
        },
        "risk_review": {
            "approved": True,
            "reason": "Risk checks pass.",
            "hard_blocks": [],
            "max_position_pct": 2.0,
        },
    }


def test_phase4_outcome_reflection_updates_prior(tmp_path):
    db_path = tmp_path / "experience_store.db"
    store = ExperienceStore(str(db_path))

    exp_id = store.record_decision(
        signature="agent-x",
        payload={"trader_proposal": {"symbol": "NSE:ITC-EQ"}},
        decision={
            "approved": True,
            "action": "BUY_CALL",
            "symbol": "NSE:ITC-EQ",
            "confidence": "MEDIUM",
            "rationale": "test",
            "risk": {"hard_blocks": []},
        },
    )

    updated = store.update_outcome_with_reflection(
        experience_id=exp_id,
        outcome_label="LOSS",
        pnl_pct=-1.2,
        reflection_note="Late entry and weak follow-through.",
        decision_quality=0.35,
        risk_efficiency=0.45,
        timing_quality=0.3,
    )

    assert updated["symbol"] == "NSE:ITC-EQ"
    assert updated["sample_count"] == 1
    assert updated["buy_call_bias"] < 0

    reloaded = ExperienceStore(str(db_path))
    prior = reloaded.get_strategy_prior(symbol="NSE:ITC-EQ")
    assert prior["sample_count"] == 1
    assert prior["buy_call_bias"] < 0

    reflections = reloaded.get_recent_reflections(symbol="NSE:ITC-EQ", limit=5)
    assert len(reflections) == 1
    assert reflections[0]["outcome_label"] == "LOSS"


def test_phase4_tool_records_outcome_and_returns_reflections(tmp_path):
    set_global_state(
        signature="agent-phase4",
        economic_tracker=None,
        task_manager=None,
        evaluator=None,
        current_date="2026-02-26",
        current_task={},
        data_path=str(tmp_path),
        supports_multimodal=True,
    )

    decision_result = institutional_desk_decide.invoke({"payload": _base_payload()})
    assert decision_result["success"] is True

    experience_id = decision_result["learning_memory"]["experience_id"]
    assert isinstance(experience_id, int)

    update_result = institutional_record_outcome.invoke(
        {
            "experience_id": experience_id,
            "outcome_label": "WIN",
            "pnl_pct": 1.8,
            "reflection_note": "Followed setup and managed risk well.",
            "decision_quality": 0.8,
            "risk_efficiency": 0.85,
            "timing_quality": 0.75,
        }
    )

    assert update_result["success"] is True
    assert update_result["updated_prior"]["sample_count"] >= 1
    assert update_result["updated_prior"]["buy_call_bias"] > 0
    assert len(update_result["recent_reflections"]) >= 1

    store_path = update_result["store_path"]
    assert isinstance(store_path, str)
    assert Path(store_path).exists()
