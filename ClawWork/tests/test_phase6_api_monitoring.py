from pathlib import Path

from fastapi.testclient import TestClient

from livebench.api import server
from livebench.trading.experience_store import ExperienceStore


def _seed_agent_store(base_data_path: Path, signature: str) -> None:
    agent_dir = base_data_path / signature
    (agent_dir / "trading").mkdir(parents=True, exist_ok=True)

    store = ExperienceStore(str(agent_dir / "trading" / "experience_store.db"))

    exp1 = store.record_decision(
        signature=signature,
        payload={"trader_proposal": {"symbol": "NSE:INFY-EQ"}},
        decision={
            "approved": True,
            "action": "BUY_CALL",
            "symbol": "NSE:INFY-EQ",
            "confidence": "MEDIUM",
            "rationale": "Aligned bullish setup",
            "risk": {"hard_blocks": []},
        },
    )
    store.update_outcome_with_reflection(
        experience_id=exp1,
        outcome_label="WIN",
        pnl_pct=1.4,
        reflection_note="Clean follow-through",
        decision_quality=0.8,
        risk_efficiency=0.85,
        timing_quality=0.75,
    )

    exp2 = store.record_decision(
        signature=signature,
        payload={"trader_proposal": {"symbol": "NSE:INFY-EQ"}},
        decision={
            "approved": False,
            "action": "NO_TRADE",
            "symbol": "NSE:INFY-EQ",
            "confidence": "LOW",
            "rationale": "Risk veto",
            "risk": {"hard_blocks": ["daily_loss_cap"]},
        },
    )
    store.update_outcome_with_reflection(
        experience_id=exp2,
        outcome_label="LOSS",
        pnl_pct=-2.3,
        reflection_note="Veto was late",
        decision_quality=0.3,
        risk_efficiency=0.4,
        timing_quality=0.25,
    )


def test_phase6_decision_cards_endpoint(monkeypatch, tmp_path):
    signature = "agent-api-phase6"
    data_path = tmp_path / "agent_data"
    _seed_agent_store(data_path, signature)

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    client = TestClient(server.app)

    response = client.get(f"/api/agents/{signature}/institutional/decision-cards", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["signature"] == signature
    assert payload["count"] >= 2
    assert isinstance(payload["cards"], list)


def test_phase6_monitoring_endpoint(monkeypatch, tmp_path):
    signature = "agent-api-phase6"
    data_path = tmp_path / "agent_data"
    _seed_agent_store(data_path, signature)

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    client = TestClient(server.app)

    response = client.get(f"/api/agents/{signature}/institutional/monitoring")
    assert response.status_code == 200

    payload = response.json()
    assert payload["signature"] == signature
    assert "monitoring" in payload
    assert "strategy_priors" in payload
    assert isinstance(payload["alerts"], list)
    assert any(alert["type"] == "drawdown_event" for alert in payload["alerts"])


def test_phase6_audit_export_json_and_csv(monkeypatch, tmp_path):
    signature = "agent-api-phase6"
    data_path = tmp_path / "agent_data"
    _seed_agent_store(data_path, signature)

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    client = TestClient(server.app)

    json_response = client.get(
        f"/api/agents/{signature}/institutional/audit-export",
        params={"fmt": "json", "limit": 10},
    )
    assert json_response.status_code == 200
    json_payload = json_response.json()
    assert json_payload["count"] >= 2
    assert isinstance(json_payload["rows"], list)

    csv_response = client.get(
        f"/api/agents/{signature}/institutional/audit-export",
        params={"fmt": "csv", "limit": 10},
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "experience_id,created_at,symbol,action" in csv_response.text
