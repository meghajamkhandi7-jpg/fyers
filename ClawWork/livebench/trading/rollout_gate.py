from __future__ import annotations

from typing import Any, Dict, List


def evaluate_rollout_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    required_checks = {
        "performance_threshold_met": bool(payload.get("performance_threshold_met", False)),
        "risk_threshold_met": bool(payload.get("risk_threshold_met", False)),
        "monitoring_active": bool(payload.get("monitoring_active", False)),
        "rollback_tested": bool(payload.get("rollback_tested", False)),
        "shadow_mode_min_days_met": bool(payload.get("shadow_mode_min_days_met", False)),
    }

    reasons = [name for name, passed in required_checks.items() if not passed]
    gate_passed = all(required_checks.values())

    rollout_plan = [
        {"stage": "stage_5pct", "allocation_pct": 5, "allowed": gate_passed},
        {"stage": "stage_25pct", "allocation_pct": 25, "allowed": gate_passed},
        {"stage": "stage_50pct", "allocation_pct": 50, "allowed": gate_passed},
        {"stage": "stage_100pct", "allocation_pct": 100, "allowed": gate_passed},
    ]

    rollback_conditions = {
        "max_drawdown_breach": bool(payload.get("max_drawdown_breach", False)),
        "daily_loss_cap_breach": bool(payload.get("daily_loss_cap_breach", False)),
        "critical_alert_active": bool(payload.get("critical_alert_active", False)),
        "manual_override_rollback": bool(payload.get("manual_override_rollback", False)),
    }
    rollback_triggered = any(rollback_conditions.values())
    rollback_reasons = [name for name, flag in rollback_conditions.items() if flag]

    deployment_decision = "ROLLBACK" if rollback_triggered else ("PROMOTE" if gate_passed else "HOLD")

    return {
        "gate_passed": gate_passed,
        "deployment_decision": deployment_decision,
        "checks": required_checks,
        "gate_fail_reasons": reasons,
        "rollout_plan": rollout_plan,
        "rollback": {
            "triggered": rollback_triggered,
            "conditions": rollback_conditions,
            "reasons": rollback_reasons,
        },
    }
