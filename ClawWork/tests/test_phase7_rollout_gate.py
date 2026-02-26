from livebench.tools.direct_tools import institutional_evaluate_rollout_gate
from livebench.trading.rollout_gate import evaluate_rollout_gate


def test_phase7_gate_promote_when_all_checks_pass():
    report = evaluate_rollout_gate(
        {
            "performance_threshold_met": True,
            "risk_threshold_met": True,
            "monitoring_active": True,
            "rollback_tested": True,
            "shadow_mode_min_days_met": True,
            "max_drawdown_breach": False,
            "daily_loss_cap_breach": False,
            "critical_alert_active": False,
            "manual_override_rollback": False,
        }
    )

    assert report["gate_passed"] is True
    assert report["deployment_decision"] == "PROMOTE"
    assert all(stage["allowed"] for stage in report["rollout_plan"])


def test_phase7_gate_hold_when_checks_fail():
    report = evaluate_rollout_gate(
        {
            "performance_threshold_met": False,
            "risk_threshold_met": True,
            "monitoring_active": True,
            "rollback_tested": True,
            "shadow_mode_min_days_met": False,
            "max_drawdown_breach": False,
            "daily_loss_cap_breach": False,
            "critical_alert_active": False,
            "manual_override_rollback": False,
        }
    )

    assert report["gate_passed"] is False
    assert report["deployment_decision"] == "HOLD"
    assert "performance_threshold_met" in report["gate_fail_reasons"]


def test_phase7_gate_rollback_overrides_promote():
    report = evaluate_rollout_gate(
        {
            "performance_threshold_met": True,
            "risk_threshold_met": True,
            "monitoring_active": True,
            "rollback_tested": True,
            "shadow_mode_min_days_met": True,
            "max_drawdown_breach": True,
            "daily_loss_cap_breach": False,
            "critical_alert_active": False,
            "manual_override_rollback": False,
        }
    )

    assert report["gate_passed"] is True
    assert report["rollback"]["triggered"] is True
    assert report["deployment_decision"] == "ROLLBACK"
    assert "max_drawdown_breach" in report["rollback"]["reasons"]


def test_phase7_tool_wrapper_success():
    payload = {
        "performance_threshold_met": True,
        "risk_threshold_met": True,
        "monitoring_active": True,
        "rollback_tested": True,
        "shadow_mode_min_days_met": True,
        "max_drawdown_breach": False,
        "daily_loss_cap_breach": False,
        "critical_alert_active": False,
        "manual_override_rollback": False,
    }
    result = institutional_evaluate_rollout_gate.invoke({"payload": payload})

    assert result["success"] is True
    assert result["report"]["deployment_decision"] == "PROMOTE"


def test_phase7_tool_wrapper_validation_error():
    result = institutional_evaluate_rollout_gate.invoke({"payload": "not-json"})

    assert result["success"] is False
    assert "payload" in result["error"].lower()
