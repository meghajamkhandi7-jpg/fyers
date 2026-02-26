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
