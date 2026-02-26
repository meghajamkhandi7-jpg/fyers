from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ExperienceStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    signature TEXT,
                    symbol TEXT,
                    action TEXT,
                    confidence TEXT,
                    approved INTEGER NOT NULL,
                    rationale TEXT,
                    risk_hard_blocks_json TEXT,
                    payload_json TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    outcome_label TEXT,
                    pnl_pct REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_experiences_symbol_created ON experiences(symbol, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_experiences_signature_created ON experiences(signature, created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experience_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    outcome_label TEXT NOT NULL,
                    pnl_pct REAL NOT NULL,
                    reflection_note TEXT,
                    decision_quality REAL,
                    risk_efficiency REAL,
                    timing_quality REAL,
                    FOREIGN KEY(experience_id) REFERENCES experiences(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflections_experience_id ON reflections(experience_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_priors (
                    symbol TEXT PRIMARY KEY,
                    buy_call_bias REAL NOT NULL,
                    buy_put_bias REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record_decision(
        self,
        *,
        signature: Optional[str],
        payload: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        symbol = str(decision.get("symbol") or payload.get("trader_proposal", {}).get("symbol") or "")
        action = str(decision.get("action") or "")
        confidence = str(decision.get("confidence") or "")
        approved = bool(decision.get("approved", False))
        rationale = str(decision.get("rationale") or "")

        risk_hard_blocks = []
        risk_section = decision.get("risk", {})
        if isinstance(risk_section, dict):
            hard_blocks = risk_section.get("hard_blocks", [])
            if isinstance(hard_blocks, list):
                risk_hard_blocks = [str(item) for item in hard_blocks]

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO experiences (
                    created_at,
                    signature,
                    symbol,
                    action,
                    confidence,
                    approved,
                    rationale,
                    risk_hard_blocks_json,
                    payload_json,
                    decision_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    signature,
                    symbol,
                    action,
                    confidence,
                    1 if approved else 0,
                    rationale,
                    json.dumps(risk_hard_blocks, ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(decision, ensure_ascii=False),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_recent(self, *, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []

        query = (
            "SELECT id, created_at, signature, symbol, action, confidence, approved, rationale, "
            "risk_hard_blocks_json, outcome_label, pnl_pct "
            "FROM experiences"
        )
        params: List[Any] = []

        if symbol and symbol.strip():
            query += " WHERE symbol = ?"
            params.append(symbol.strip())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            risk_hard_blocks = []
            if row[8]:
                try:
                    parsed = json.loads(row[8])
                    if isinstance(parsed, list):
                        risk_hard_blocks = [str(item) for item in parsed]
                except json.JSONDecodeError:
                    risk_hard_blocks = []

            results.append(
                {
                    "experience_id": int(row[0]),
                    "created_at": row[1],
                    "signature": row[2],
                    "symbol": row[3],
                    "action": row[4],
                    "confidence": row[5],
                    "approved": bool(row[6]),
                    "rationale": row[7],
                    "risk_hard_blocks": risk_hard_blocks,
                    "outcome_label": row[9],
                    "pnl_pct": row[10],
                }
            )

        return results

    def update_outcome(self, *, experience_id: int, outcome_label: str, pnl_pct: float) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE experiences SET outcome_label = ?, pnl_pct = ? WHERE id = ?",
                (outcome_label, float(pnl_pct), int(experience_id)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_strategy_prior(self, *, symbol: str) -> Dict[str, Any]:
        clean_symbol = symbol.strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT symbol, buy_call_bias, buy_put_bias, sample_count, updated_at FROM strategy_priors WHERE symbol = ?",
                (clean_symbol,),
            ).fetchone()

        if row is None:
            return {
                "symbol": clean_symbol,
                "buy_call_bias": 0.0,
                "buy_put_bias": 0.0,
                "sample_count": 0,
                "updated_at": None,
            }

        return {
            "symbol": row[0],
            "buy_call_bias": float(row[1]),
            "buy_put_bias": float(row[2]),
            "sample_count": int(row[3]),
            "updated_at": row[4],
        }

    def get_recent_reflections(self, *, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []

        query = (
            "SELECT r.id, r.experience_id, r.created_at, r.outcome_label, r.pnl_pct, r.reflection_note, "
            "r.decision_quality, r.risk_efficiency, r.timing_quality, e.symbol "
            "FROM reflections r JOIN experiences e ON e.id = r.experience_id"
        )
        params: List[Any] = []

        if symbol and symbol.strip():
            query += " WHERE e.symbol = ?"
            params.append(symbol.strip())

        query += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "reflection_id": int(row[0]),
                "experience_id": int(row[1]),
                "created_at": row[2],
                "outcome_label": row[3],
                "pnl_pct": float(row[4]),
                "reflection_note": row[5],
                "decision_quality": row[6],
                "risk_efficiency": row[7],
                "timing_quality": row[8],
                "symbol": row[9],
            }
            for row in rows
        ]

    def update_outcome_with_reflection(
        self,
        *,
        experience_id: int,
        outcome_label: str,
        pnl_pct: float,
        reflection_note: str = "",
        decision_quality: Optional[float] = None,
        risk_efficiency: Optional[float] = None,
        timing_quality: Optional[float] = None,
    ) -> Dict[str, Any]:
        clean_outcome = outcome_label.strip().upper()
        if clean_outcome not in {"WIN", "LOSS", "BREAKEVEN"}:
            raise ValueError("outcome_label must be one of: WIN, LOSS, BREAKEVEN")

        if not self.update_outcome(experience_id=experience_id, outcome_label=clean_outcome, pnl_pct=pnl_pct):
            raise ValueError(f"experience_id not found: {experience_id}")

        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reflections (
                    experience_id,
                    created_at,
                    outcome_label,
                    pnl_pct,
                    reflection_note,
                    decision_quality,
                    risk_efficiency,
                    timing_quality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(experience_id),
                    now,
                    clean_outcome,
                    float(pnl_pct),
                    reflection_note,
                    decision_quality,
                    risk_efficiency,
                    timing_quality,
                ),
            )

            row = conn.execute(
                "SELECT symbol, action FROM experiences WHERE id = ?",
                (int(experience_id),),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise ValueError(f"experience_id not found after update: {experience_id}")

            symbol = str(row[0] or "").strip()
            action = str(row[1] or "").strip().upper()

            prior_row = conn.execute(
                "SELECT buy_call_bias, buy_put_bias, sample_count FROM strategy_priors WHERE symbol = ?",
                (symbol,),
            ).fetchone()

            if prior_row is None:
                buy_call_bias = 0.0
                buy_put_bias = 0.0
                sample_count = 0
            else:
                buy_call_bias = float(prior_row[0])
                buy_put_bias = float(prior_row[1])
                sample_count = int(prior_row[2])

            if clean_outcome == "WIN":
                reward = 1.0
            elif clean_outcome == "LOSS":
                reward = -1.0
            else:
                reward = 0.0

            learning_rate = 0.1

            if action == "BUY_CALL":
                buy_call_bias = max(-1.0, min(1.0, buy_call_bias + learning_rate * reward))
            elif action == "BUY_PUT":
                buy_put_bias = max(-1.0, min(1.0, buy_put_bias + learning_rate * reward))

            sample_count += 1

            conn.execute(
                """
                INSERT INTO strategy_priors (symbol, buy_call_bias, buy_put_bias, sample_count, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    buy_call_bias = excluded.buy_call_bias,
                    buy_put_bias = excluded.buy_put_bias,
                    sample_count = excluded.sample_count,
                    updated_at = excluded.updated_at
                """,
                (symbol, buy_call_bias, buy_put_bias, sample_count, now),
            )

            conn.commit()

        return self.get_strategy_prior(symbol=symbol)
