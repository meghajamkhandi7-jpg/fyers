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

    if not risk.approved or risk.hard_blocks:
        return {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approved": False,
            "action": "NO_TRADE",
            "symbol": trader.symbol,
            "quantity": 0,
            "confidence": "LOW",
            "rationale": f"Risk manager veto: {risk.reason}",
            "risk": {
                "approved": risk.approved,
                "reason": risk.reason,
                "hard_blocks": risk.hard_blocks,
                "max_position_pct": risk.max_position_pct,
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
                "hard_blocks": risk.hard_blocks,
                "max_position_pct": risk.max_position_pct,
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
                "hard_blocks": risk.hard_blocks,
                "max_position_pct": risk.max_position_pct,
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
            "hard_blocks": risk.hard_blocks,
            "max_position_pct": risk.max_position_pct,
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
