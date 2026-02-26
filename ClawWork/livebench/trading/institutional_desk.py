from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal


DeskAction = Literal["BUY_CALL", "BUY_PUT", "NO_TRADE"]
DeskConfidence = Literal["LOW", "MEDIUM", "HIGH"]
AnalystRole = Literal["technical", "fundamental", "sentiment"]
AnalystStance = Literal["BULLISH", "BEARISH", "NEUTRAL"]

CONFIDENCE_SCORE: Dict[str, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
ALLOWED_ACTIONS = {"BUY_CALL", "BUY_PUT", "NO_TRADE"}
ALLOWED_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_ROLES = {"technical", "fundamental", "sentiment"}
ALLOWED_STANCES = {"BULLISH", "BEARISH", "NEUTRAL"}
SCHEMA_VERSION = "phase1.v1"


@dataclass(frozen=True)
class AnalystOutput:
    role: AnalystRole
    stance: AnalystStance
    confidence: DeskConfidence
    rationale: str
    evidence: List[str]


@dataclass(frozen=True)
class TraderProposal:
    action: DeskAction
    symbol: str
    quantity: int
    confidence: DeskConfidence
    rationale: str
    risk_budget_pct: float


@dataclass(frozen=True)
class RiskReview:
    approved: bool
    reason: str
    hard_blocks: List[str]
    max_position_pct: float


@dataclass(frozen=True)
class PolicyEvaluation:
    hard_blocks: List[str]
    checks: Dict[str, Any]


def _require_keys(data: Dict[str, Any], required: List[str], section: str) -> None:
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"{section} missing required keys: {missing}")


def _validate_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _parse_analyst_output(data: Dict[str, Any]) -> AnalystOutput:
    _require_keys(data, ["role", "stance", "confidence", "rationale", "evidence"], "analyst")

    role = _validate_non_empty_text(data["role"], "analyst.role").lower()
    if role not in ALLOWED_ROLES:
        raise ValueError(f"analyst.role must be one of {sorted(ALLOWED_ROLES)}")

    stance = _validate_non_empty_text(data["stance"], "analyst.stance").upper()
    if stance not in ALLOWED_STANCES:
        raise ValueError(f"analyst.stance must be one of {sorted(ALLOWED_STANCES)}")

    confidence = _validate_non_empty_text(data["confidence"], "analyst.confidence").upper()
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"analyst.confidence must be one of {sorted(ALLOWED_CONFIDENCE)}")

    rationale = _validate_non_empty_text(data["rationale"], "analyst.rationale")

    evidence = data["evidence"]
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
        raise ValueError("analyst.evidence must be a non-empty list of strings")

    return AnalystOutput(
        role=role,  # type: ignore[arg-type]
        stance=stance,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        rationale=rationale,
        evidence=[item.strip() for item in evidence],
    )


def _parse_trader_proposal(data: Dict[str, Any]) -> TraderProposal:
    _require_keys(
        data,
        ["action", "symbol", "quantity", "confidence", "rationale", "risk_budget_pct"],
        "trader_proposal",
    )

    action = _validate_non_empty_text(data["action"], "trader_proposal.action").upper()
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"trader_proposal.action must be one of {sorted(ALLOWED_ACTIONS)}")

    symbol = _validate_non_empty_text(data["symbol"], "trader_proposal.symbol")

    quantity = data["quantity"]
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("trader_proposal.quantity must be a positive integer")

    confidence = _validate_non_empty_text(data["confidence"], "trader_proposal.confidence").upper()
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"trader_proposal.confidence must be one of {sorted(ALLOWED_CONFIDENCE)}")

    rationale = _validate_non_empty_text(data["rationale"], "trader_proposal.rationale")

    risk_budget_pct = data["risk_budget_pct"]
    if not isinstance(risk_budget_pct, (int, float)) or risk_budget_pct <= 0 or risk_budget_pct > 100:
        raise ValueError("trader_proposal.risk_budget_pct must be a number in (0, 100]")

    return TraderProposal(
        action=action,  # type: ignore[arg-type]
        symbol=symbol,
        quantity=quantity,
        confidence=confidence,  # type: ignore[arg-type]
        rationale=rationale,
        risk_budget_pct=float(risk_budget_pct),
    )


def _parse_risk_review(data: Dict[str, Any]) -> RiskReview:
    _require_keys(data, ["approved", "reason", "hard_blocks", "max_position_pct"], "risk_review")

    approved = data["approved"]
    if not isinstance(approved, bool):
        raise ValueError("risk_review.approved must be a boolean")

    reason = _validate_non_empty_text(data["reason"], "risk_review.reason")

    hard_blocks = data["hard_blocks"]
    if not isinstance(hard_blocks, list) or not all(isinstance(item, str) for item in hard_blocks):
        raise ValueError("risk_review.hard_blocks must be a list of strings")

    max_position_pct = data["max_position_pct"]
    if not isinstance(max_position_pct, (int, float)) or max_position_pct <= 0 or max_position_pct > 100:
        raise ValueError("risk_review.max_position_pct must be a number in (0, 100]")

    return RiskReview(
        approved=approved,
        reason=reason,
        hard_blocks=[item.strip() for item in hard_blocks if item.strip()],
        max_position_pct=float(max_position_pct),
    )


def _evaluate_policy_vetoes(
    *,
    symbol: str,
    trader: TraderProposal,
    risk_context: Dict[str, Any],
) -> PolicyEvaluation:
    checks: Dict[str, Any] = {}
    hard_blocks: List[str] = []

    daily_pnl_pct = float(risk_context.get("daily_realized_pnl_pct", 0.0))
    max_daily_loss_pct = float(risk_context.get("max_daily_loss_pct", 2.0))
    checks["daily_loss_guard"] = {
        "value": daily_pnl_pct,
        "threshold": -abs(max_daily_loss_pct),
        "status": "PASS" if daily_pnl_pct > -abs(max_daily_loss_pct) else "FAIL",
    }
    if checks["daily_loss_guard"]["status"] == "FAIL":
        hard_blocks.append("daily_loss_cap")

    per_trade_risk_pct = float(risk_context.get("per_trade_risk_pct", 0.0))
    max_per_trade_risk_pct = float(risk_context.get("max_per_trade_risk_pct", 0.5))
    checks["per_trade_risk_guard"] = {
        "value": per_trade_risk_pct,
        "threshold": max_per_trade_risk_pct,
        "status": "PASS" if per_trade_risk_pct <= max_per_trade_risk_pct else "FAIL",
    }
    if checks["per_trade_risk_guard"]["status"] == "FAIL":
        hard_blocks.append("per_trade_risk_cap")

    concurrent_positions = int(risk_context.get("concurrent_positions", 0))
    max_concurrent_positions = int(risk_context.get("max_concurrent_positions", 2))
    checks["concurrent_positions_guard"] = {
        "value": concurrent_positions,
        "threshold": max_concurrent_positions,
        "status": "PASS" if concurrent_positions < max_concurrent_positions else "FAIL",
    }
    if checks["concurrent_positions_guard"]["status"] == "FAIL":
        hard_blocks.append("max_concurrent_positions")

    symbol_exposure_pct = float(risk_context.get("symbol_exposure_pct", 0.0))
    max_symbol_exposure_pct = float(risk_context.get("max_symbol_exposure_pct", 60.0))
    checks["symbol_exposure_guard"] = {
        "value": symbol_exposure_pct,
        "threshold": max_symbol_exposure_pct,
        "status": "PASS" if symbol_exposure_pct <= max_symbol_exposure_pct else "FAIL",
    }
    if checks["symbol_exposure_guard"]["status"] == "FAIL":
        hard_blocks.append("max_underlying_exposure")

    data_completeness_pct = float(risk_context.get("data_completeness_pct", 100.0))
    min_data_completeness_pct = float(risk_context.get("min_data_completeness_pct", 95.0))
    checks["data_quality_guard"] = {
        "value": data_completeness_pct,
        "threshold": min_data_completeness_pct,
        "status": "PASS" if data_completeness_pct >= min_data_completeness_pct else "FAIL",
    }
    if checks["data_quality_guard"]["status"] == "FAIL":
        hard_blocks.append("data_quality")

    bid_ask_spread_bps = float(risk_context.get("bid_ask_spread_bps", 0.0))
    max_bid_ask_spread_bps = float(risk_context.get("max_bid_ask_spread_bps", 50.0))
    checks["liquidity_guard"] = {
        "value": bid_ask_spread_bps,
        "threshold": max_bid_ask_spread_bps,
        "status": "PASS" if bid_ask_spread_bps <= max_bid_ask_spread_bps else "FAIL",
    }
    if checks["liquidity_guard"]["status"] == "FAIL":
        hard_blocks.append("liquidity_spread")

    event_blackout = bool(risk_context.get("event_blackout", False))
    checks["event_blackout_guard"] = {
        "value": event_blackout,
        "status": "FAIL" if event_blackout else "PASS",
    }
    if checks["event_blackout_guard"]["status"] == "FAIL":
        hard_blocks.append("event_blackout")

    available_risk_budget_pct = float(risk_context.get("available_risk_budget_pct", 100.0))
    checks["risk_budget_guard"] = {
        "value": available_risk_budget_pct,
        "threshold": 0.0,
        "status": "PASS" if available_risk_budget_pct > 0 else "FAIL",
    }
    if checks["risk_budget_guard"]["status"] == "FAIL":
        hard_blocks.append("risk_budget_unavailable")

    restricted_symbols = risk_context.get("restricted_symbols", [])
    if restricted_symbols is None:
        restricted_symbols = []
    if not isinstance(restricted_symbols, list):
        raise ValueError("risk_context.restricted_symbols must be a list")
    restricted_set = {str(item).strip().upper() for item in restricted_symbols if str(item).strip()}
    symbol_upper = symbol.strip().upper()
    checks["restricted_symbol_guard"] = {
        "value": symbol_upper,
        "status": "FAIL" if symbol_upper in restricted_set else "PASS",
    }
    if checks["restricted_symbol_guard"]["status"] == "FAIL":
        hard_blocks.append("restricted_symbol")

    return PolicyEvaluation(
        hard_blocks=sorted(set(hard_blocks)),
        checks=checks,
    )


def _expected_action_from_votes(analysts: List[AnalystOutput]) -> DeskAction:
    bullish_score = sum(CONFIDENCE_SCORE[item.confidence] for item in analysts if item.stance == "BULLISH")
    bearish_score = sum(CONFIDENCE_SCORE[item.confidence] for item in analysts if item.stance == "BEARISH")

    if bullish_score >= bearish_score + 2:
        return "BUY_CALL"
    if bearish_score >= bullish_score + 2:
        return "BUY_PUT"
    return "NO_TRADE"


def _consensus_confidence(analysts: List[AnalystOutput], expected_action: DeskAction) -> DeskConfidence:
    if expected_action == "NO_TRADE":
        return "LOW"

    target_stance = "BULLISH" if expected_action == "BUY_CALL" else "BEARISH"
    score = sum(CONFIDENCE_SCORE[item.confidence] for item in analysts if item.stance == target_stance)

    if score >= 8:
        return "HIGH"
    if score >= 5:
        return "MEDIUM"
    return "LOW"


def run_institutional_desk(payload: Dict[str, Any]) -> Dict[str, Any]:
    _require_keys(payload, ["analysts", "trader_proposal", "risk_review"], "payload")

    analysts_raw = payload["analysts"]
    if not isinstance(analysts_raw, list) or len(analysts_raw) < 3:
        raise ValueError("payload.analysts must be a list with at least 3 analyst outputs")

    analysts = [_parse_analyst_output(item) for item in analysts_raw]

    seen_roles = {item.role for item in analysts}
    if seen_roles != ALLOWED_ROLES:
        raise ValueError("payload.analysts must include exactly these roles: technical, fundamental, sentiment")

    trader = _parse_trader_proposal(payload["trader_proposal"])
    risk = _parse_risk_review(payload["risk_review"])
    risk_context_raw = payload.get("risk_context", {})
    if risk_context_raw is None:
        risk_context_raw = {}
    if not isinstance(risk_context_raw, dict):
        raise ValueError("payload.risk_context must be an object when provided")

    policy_eval = _evaluate_policy_vetoes(
        symbol=trader.symbol,
        trader=trader,
        risk_context=risk_context_raw,
    )
    combined_hard_blocks = sorted(set(risk.hard_blocks + policy_eval.hard_blocks))

    if not risk.approved or combined_hard_blocks:
        veto_reason = risk.reason if not risk.approved else "Policy veto triggered"
        return {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approved": False,
            "action": "NO_TRADE",
            "symbol": trader.symbol,
            "quantity": 0,
            "confidence": "LOW",
            "rationale": f"Risk manager veto: {veto_reason}",
            "risk": {
                "approved": risk.approved,
                "reason": risk.reason,
                "hard_blocks": combined_hard_blocks,
                "max_position_pct": risk.max_position_pct,
                "policy_checks": policy_eval.checks,
            },
            "role_votes": [
                {
                    "role": item.role,
                    "stance": item.stance,
                    "confidence": item.confidence,
                    "rationale": item.rationale,
                }
                for item in analysts
            ],
            "evidence": [entry for item in analysts for entry in item.evidence],
        }

    expected_action = _expected_action_from_votes(analysts)

    if expected_action == "NO_TRADE":
        return {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approved": False,
            "action": "NO_TRADE",
            "symbol": trader.symbol,
            "quantity": 0,
            "confidence": "LOW",
            "rationale": "No directional consensus among analysts.",
            "risk": {
                "approved": risk.approved,
                "reason": risk.reason,
                "hard_blocks": combined_hard_blocks,
                "max_position_pct": risk.max_position_pct,
                "policy_checks": policy_eval.checks,
            },
            "role_votes": [
                {
                    "role": item.role,
                    "stance": item.stance,
                    "confidence": item.confidence,
                    "rationale": item.rationale,
                }
                for item in analysts
            ],
            "evidence": [entry for item in analysts for entry in item.evidence],
        }

    if trader.action != expected_action:
        return {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approved": False,
            "action": "NO_TRADE",
            "symbol": trader.symbol,
            "quantity": 0,
            "confidence": "LOW",
            "rationale": "Trader proposal is misaligned with analyst consensus.",
            "risk": {
                "approved": risk.approved,
                "reason": risk.reason,
                "hard_blocks": combined_hard_blocks,
                "max_position_pct": risk.max_position_pct,
                "policy_checks": policy_eval.checks,
            },
            "role_votes": [
                {
                    "role": item.role,
                    "stance": item.stance,
                    "confidence": item.confidence,
                    "rationale": item.rationale,
                }
                for item in analysts
            ],
            "evidence": [entry for item in analysts for entry in item.evidence],
        }

    decision_confidence = _consensus_confidence(analysts, expected_action)

    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "approved": True,
        "action": trader.action,
        "symbol": trader.symbol,
        "quantity": trader.quantity,
        "confidence": decision_confidence,
        "rationale": trader.rationale,
        "risk": {
            "approved": risk.approved,
            "reason": risk.reason,
            "hard_blocks": combined_hard_blocks,
            "max_position_pct": risk.max_position_pct,
            "policy_checks": policy_eval.checks,
        },
        "role_votes": [
            {
                "role": item.role,
                "stance": item.stance,
                "confidence": item.confidence,
                "rationale": item.rationale,
            }
            for item in analysts
        ],
        "evidence": [entry for item in analysts for entry in item.evidence],
    }
