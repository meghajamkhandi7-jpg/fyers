"""
LiveBench API Server - Real-time updates and data access for frontend

This FastAPI server provides:
- WebSocket endpoint for live agent activity streaming
- REST endpoints for agent data, tasks, and economic metrics
- Real-time updates as agents work and learn
"""

import os
import json
import asyncio
import random
import re
import sqlite3
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import glob

app = FastAPI(title="LiveBench API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data path
DATA_PATH = Path(__file__).parent.parent / "data" / "agent_data"
HIDDEN_AGENTS_PATH = Path(__file__).parent.parent / "data" / "hidden_agents.json"
FYERS_DATA_PATH = Path(__file__).parent.parent / "data" / "fyers"

# Task value lookup (task_id -> task_value_usd)
_TASK_VALUES_PATH = Path(__file__).parent.parent.parent / "scripts" / "task_value_estimates" / "task_values.jsonl"


def _load_task_values() -> dict:
    values = {}
    if not _TASK_VALUES_PATH.exists():
        return values
    with open(_TASK_VALUES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                tid = entry.get("task_id")
                val = entry.get("task_value_usd")
                if tid and val is not None:
                    values[tid] = val
            except json.JSONDecodeError:
                pass
    return values


TASK_VALUES = _load_task_values()


def _extract_sim_date_from_system(messages: list) -> Optional[str]:
    for message in messages or []:
        if message.get("role") != "system":
            continue
        content = message.get("content") or ""
        match = re.search(r"CURRENT ECONOMIC STATUS\s*-\s*(\d{4}-\d{2}-\d{2})", content)
        if match:
            return match.group(1)
    return None


def _infer_activity_from_messages(messages: list) -> Optional[str]:
    combined = "\n".join((msg.get("content") or "") for msg in (messages or []))
    lowered = combined.lower()
    if any(token in lowered for token in ["submit_work", "work task", "lending recommendation", "curriculum", "credit risk"]):
        return "work"
    if any(token in lowered for token in ["learn(", "learn topic", "research and learn", "save_to_memory"]):
        return "learn"
    return None


def _extract_reasoning_from_messages(messages: list) -> str:
    for message in messages or []:
        if message.get("role") != "assistant":
            continue
        content = (message.get("content") or "").strip()
        if content:
            compact = " ".join(content.split())
            return compact[:200]
    return "Recovered from activity logs"


def _load_decisions_from_activity_logs(agent_dir: Path) -> List[dict]:
    activity_root = agent_dir / "activity_logs"
    if not activity_root.exists():
        return []

    recovered = []
    for log_path in sorted(activity_root.glob("**/log.jsonl")):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                messages = entry.get("messages", [])
                activity = _infer_activity_from_messages(messages)
                if not activity:
                    continue

                sim_date = _extract_sim_date_from_system(messages)
                if not sim_date:
                    timestamp = (entry.get("timestamp") or "")
                    sim_date = timestamp[:10] if len(timestamp) >= 10 else ""

                recovered.append({
                    "activity": activity,
                    "date": sim_date,
                    "reasoning": _extract_reasoning_from_messages(messages),
                    "source": "activity_logs",
                })

    return recovered


def _resolve_agent_trading_dir(signature: str) -> Path:
    return DATA_PATH / signature / "trading"


def _resolve_experience_store_path(signature: str) -> Path:
    return _resolve_agent_trading_dir(signature) / "experience_store.db"


def _fetch_institutional_rows(signature: str, limit: int = 50) -> List[dict]:
    store_path = _resolve_experience_store_path(signature)
    if not store_path.exists():
        return []

    with sqlite3.connect(store_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.created_at,
                e.symbol,
                e.action,
                e.confidence,
                e.approved,
                e.rationale,
                e.risk_hard_blocks_json,
                e.outcome_label,
                e.pnl_pct,
                r.reflection_note,
                r.decision_quality,
                r.risk_efficiency,
                r.timing_quality
            FROM experiences e
            LEFT JOIN reflections r ON r.experience_id = e.id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    result = []
    for row in rows:
        hard_blocks = []
        if row[7]:
            try:
                parsed = json.loads(row[7])
                if isinstance(parsed, list):
                    hard_blocks = [str(item) for item in parsed]
            except json.JSONDecodeError:
                hard_blocks = []

        result.append(
            {
                "experience_id": int(row[0]),
                "created_at": row[1],
                "symbol": row[2],
                "action": row[3],
                "confidence": row[4],
                "approved": bool(row[5]),
                "rationale": row[6],
                "risk_hard_blocks": hard_blocks,
                "outcome_label": row[8],
                "pnl_pct": row[9],
                "reflection_note": row[10],
                "decision_quality": row[11],
                "risk_efficiency": row[12],
                "timing_quality": row[13],
            }
        )

    return result


def _fetch_strategy_priors(signature: str) -> List[dict]:
    store_path = _resolve_experience_store_path(signature)
    if not store_path.exists():
        return []

    with sqlite3.connect(store_path) as conn:
        rows = conn.execute(
            """
            SELECT symbol, buy_call_bias, buy_put_bias, sample_count, updated_at
            FROM strategy_priors
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return [
        {
            "symbol": row[0],
            "buy_call_bias": float(row[1]),
            "buy_put_bias": float(row[2]),
            "sample_count": int(row[3]),
            "updated_at": row[4],
        }
        for row in rows
    ]


def _build_institutional_alerts(rows: List[dict]) -> List[dict]:
    alerts: List[dict] = []
    if not rows:
        return alerts

    recent = rows[:20]
    veto_count = sum(1 for row in recent if not row.get("approved", False))
    veto_rate = (veto_count / len(recent)) if recent else 0.0
    if veto_rate >= 0.6 and len(recent) >= 5:
        alerts.append(
            {
                "type": "veto_spike",
                "severity": "warning",
                "message": f"High veto rate in recent decisions: {veto_rate * 100:.1f}%",
            }
        )

    pnl_values = [float(row.get("pnl_pct")) for row in recent if row.get("pnl_pct") is not None]
    if pnl_values:
        worst = min(pnl_values)
        if worst <= -2.0:
            alerts.append(
                {
                    "type": "drawdown_event",
                    "severity": "critical",
                    "message": f"Severe single-trade drawdown observed: {worst:.2f}%",
                }
            )

    return alerts

# Active WebSocket connections
active_connections: List[WebSocket] = []


class AgentStatus(BaseModel):
    """Agent status model"""
    signature: str
    balance: float
    net_worth: float
    survival_status: str
    current_activity: Optional[str] = None
    current_date: Optional[str] = None


class WorkTask(BaseModel):
    """Work task model"""
    task_id: str
    sector: str
    occupation: str
    prompt: str
    date: str
    status: str = "assigned"


class LearningEntry(BaseModel):
    """Learning memory entry"""
    topic: str
    content: str
    timestamp: str


class EconomicMetrics(BaseModel):
    """Economic metrics model"""
    balance: float
    total_token_cost: float
    total_work_income: float
    net_worth: float
    dates: List[str]
    balance_history: List[float]


# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "LiveBench API",
        "version": "1.0.0",
        "endpoints": {
            "agents": "/api/agents",
            "agent_detail": "/api/agents/{signature}",
            "tasks": "/api/agents/{signature}/tasks",
            "learning": "/api/agents/{signature}/learning",
            "economic": "/api/agents/{signature}/economic",
            "websocket": "/ws"
        }
    }


@app.get("/api/agents")
async def get_agents():
    """Get list of all agents with their current status"""
    agents = []

    if not DATA_PATH.exists():
        return {"agents": []}

    for agent_dir in DATA_PATH.iterdir():
        if agent_dir.is_dir():
            signature = agent_dir.name

            # Get latest balance
            balance_file = agent_dir / "economic" / "balance.jsonl"
            balance_data = None
            if balance_file.exists():
                with open(balance_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        balance_data = json.loads(lines[-1])

            # Get latest decision
            decision_file = agent_dir / "decisions" / "decisions.jsonl"
            current_activity = None
            current_date = None
            if decision_file.exists():
                with open(decision_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        decision = json.loads(lines[-1])
                        current_activity = decision.get("activity")
                        current_date = decision.get("date")

            if balance_data:
                agents.append({
                    "signature": signature,
                    "balance": balance_data.get("balance", 0),
                    "net_worth": balance_data.get("net_worth", 0),
                    "survival_status": balance_data.get("survival_status", "unknown"),
                    "current_activity": current_activity,
                    "current_date": current_date,
                    "total_token_cost": balance_data.get("total_token_cost", 0)
                })

    return {"agents": agents}


@app.get("/api/agents/{signature}")
async def get_agent_details(signature: str):
    """Get detailed information about a specific agent"""
    agent_dir = DATA_PATH / signature

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get balance history
    balance_file = agent_dir / "economic" / "balance.jsonl"
    balance_history = []
    if balance_file.exists():
        with open(balance_file, 'r') as f:
            for line in f:
                balance_history.append(json.loads(line))

    # Get decisions
    decision_file = agent_dir / "decisions" / "decisions.jsonl"
    decisions = []
    if decision_file.exists():
        with open(decision_file, 'r') as f:
            for line in f:
                decisions.append(json.loads(line))
    else:
        decisions = _load_decisions_from_activity_logs(agent_dir)

    # Get evaluation statistics
    evaluations_file = agent_dir / "work" / "evaluations.jsonl"
    avg_evaluation_score = None
    evaluation_scores = []
    
    if evaluations_file.exists():
        with open(evaluations_file, 'r') as f:
            for line in f:
                eval_data = json.loads(line)
                score = eval_data.get("evaluation_score")
                if score is not None:
                    evaluation_scores.append(score)
        
        if evaluation_scores:
            avg_evaluation_score = sum(evaluation_scores) / len(evaluation_scores)
    
    # Get latest status
    latest_balance = balance_history[-1] if balance_history else {}
    latest_decision = decisions[-1] if decisions else {}

    return {
        "signature": signature,
        "current_status": {
            "balance": latest_balance.get("balance", 0),
            "net_worth": latest_balance.get("net_worth", 0),
            "survival_status": latest_balance.get("survival_status", "unknown"),
            "total_token_cost": latest_balance.get("total_token_cost", 0),
            "total_work_income": latest_balance.get("total_work_income", 0),
            "current_activity": latest_decision.get("activity"),
            "current_date": latest_decision.get("date"),
            "avg_evaluation_score": avg_evaluation_score,  # Average 0.0-1.0 score
            "num_evaluations": len(evaluation_scores)
        },
        "balance_history": balance_history,
        "decisions": decisions,
        "evaluation_scores": evaluation_scores  # List of all scores
    }


@app.get("/api/agents/{signature}/tasks")
async def get_agent_tasks(signature: str):
    """Get all tasks assigned to an agent"""
    agent_dir = DATA_PATH / signature

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    tasks_file = agent_dir / "work" / "tasks.jsonl"
    evaluations_file = agent_dir / "work" / "evaluations.jsonl"

    tasks = []
    if tasks_file.exists():
        with open(tasks_file, 'r') as f:
            for line in f:
                tasks.append(json.loads(line))

    # Load evaluations grouped by task_id (preserve order)
    evaluations = {}
    if evaluations_file.exists():
        with open(evaluations_file, 'r') as f:
            for line in f:
                eval_data = json.loads(line)
                task_id = eval_data.get("task_id")
                if task_id:
                    if task_id not in evaluations:
                        evaluations[task_id] = []
                    evaluations[task_id].append(eval_data)

    # Merge tasks with evaluations
    for task in tasks:
        task_id = task.get("task_id")
        # Inject task market value if available
        if task_id and task_id in TASK_VALUES:
            task["task_value_usd"] = TASK_VALUES[task_id]
        evaluation_list = evaluations.get(task_id, [])
        evaluation = evaluation_list.pop(0) if evaluation_list else None
        if evaluation is not None:
            task["evaluation"] = evaluation
            task["completed"] = True
            task["payment"] = evaluation.get("payment", 0)
            task["feedback"] = evaluation.get("feedback", "")
            task["evaluation_score"] = evaluation.get("evaluation_score", None)  # 0.0-1.0 scale
            task["evaluation_method"] = evaluation.get("evaluation_method", "heuristic")
        else:
            task["completed"] = False
            task["payment"] = 0
            task["evaluation_score"] = None

    return {"tasks": tasks}


@app.get("/api/agents/{signature}/terminal-log/{date}")
async def get_terminal_log(signature: str, date: str):
    """Get terminal log for an agent on a specific date"""
    agent_dir = DATA_PATH / signature
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")
    log_file = agent_dir / "terminal_logs" / f"{date}.log"
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log not found")
    content = log_file.read_text(encoding="utf-8", errors="replace")
    return {"date": date, "content": content}


@app.get("/api/agents/{signature}/learning")
async def get_agent_learning(signature: str):
    """Get agent's learning memory"""
    agent_dir = DATA_PATH / signature

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    memory_file = agent_dir / "memory" / "memory.jsonl"

    if not memory_file.exists():
        return {"memory": "", "entries": []}

    # Parse JSONL format
    entries = []
    with open(memory_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                entries.append({
                    "topic": entry.get("topic", "Unknown"),
                    "timestamp": entry.get("timestamp", ""),
                    "date": entry.get("date", ""),
                    "content": entry.get("knowledge", "")
                })

    # Create a summary memory content
    memory_content = "\n\n".join([
        f"## {entry['topic']} ({entry['date']})\n{entry['content']}"
        for entry in entries
    ])

    return {
        "memory": memory_content,
        "entries": entries
    }


@app.get("/api/agents/{signature}/economic")
async def get_agent_economic(signature: str):
    """Get economic metrics for an agent"""
    agent_dir = DATA_PATH / signature

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    balance_file = agent_dir / "economic" / "balance.jsonl"

    if not balance_file.exists():
        raise HTTPException(status_code=404, detail="No economic data found")

    dates = []
    balance_history = []
    token_costs = []
    work_income = []

    with open(balance_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            dates.append(data.get("date", ""))
            balance_history.append(data.get("balance", 0))
            token_costs.append(data.get("daily_token_cost", 0))
            work_income.append(data.get("work_income_delta", 0))

    latest = json.loads(line) if line else {}

    return {
        "balance": latest.get("balance", 0),
        "total_token_cost": latest.get("total_token_cost", 0),
        "total_work_income": latest.get("total_work_income", 0),
        "net_worth": latest.get("net_worth", 0),
        "survival_status": latest.get("survival_status", "unknown"),
        "dates": dates,
        "balance_history": balance_history,
        "token_costs": token_costs,
        "work_income": work_income
    }


@app.get("/api/leaderboard")
async def get_leaderboard():
    """Get leaderboard data for all agents with summary metrics and balance histories"""
    if not DATA_PATH.exists():
        return {"agents": []}

    agents = []

    for agent_dir in DATA_PATH.iterdir():
        if not agent_dir.is_dir():
            continue

        signature = agent_dir.name

        # Load balance history
        balance_file = agent_dir / "economic" / "balance.jsonl"
        balance_history = []
        if balance_file.exists():
            with open(balance_file, 'r') as f:
                for line in f:
                    if line.strip():
                        balance_history.append(json.loads(line))

        if not balance_history:
            continue

        latest = balance_history[-1]
        initial_balance = balance_history[0].get("balance", 0)
        current_balance = latest.get("balance", 0)
        pct_change = ((current_balance - initial_balance) / initial_balance * 100) if initial_balance else 0

        # Load evaluation scores
        evaluations_file = agent_dir / "work" / "evaluations.jsonl"
        evaluation_scores = []
        if evaluations_file.exists():
            with open(evaluations_file, 'r') as f:
                for line in f:
                    if line.strip():
                        eval_data = json.loads(line)
                        score = eval_data.get("evaluation_score")
                        if score is not None:
                            evaluation_scores.append(score)

        avg_eval_score = (sum(evaluation_scores) / len(evaluation_scores)) if evaluation_scores else None

        # Strip balance history to essential fields, exclude initialization
        stripped_history = [
            {
                "date": entry.get("date"),
                "balance": entry.get("balance", 0),
                "task_completion_time_seconds": entry.get("task_completion_time_seconds"),
            }
            for entry in balance_history
            if entry.get("date") != "initialization"
        ]

        agents.append({
            "signature": signature,
            "initial_balance": initial_balance,
            "current_balance": current_balance,
            "pct_change": round(pct_change, 1),
            "total_token_cost": latest.get("total_token_cost", 0),
            "total_work_income": latest.get("total_work_income", 0),
            "net_worth": latest.get("net_worth", 0),
            "survival_status": latest.get("survival_status", "unknown"),
            "num_tasks": len(evaluation_scores),
            "avg_eval_score": avg_eval_score,
            "balance_history": stripped_history,
        })

    # Sort by current_balance descending
    agents.sort(key=lambda a: a["current_balance"], reverse=True)

    return {"agents": agents}


@app.get("/api/fyers/screener/latest")
async def get_latest_fyers_screener():
    """Get the most recent FYERS screener output JSON."""
    if not FYERS_DATA_PATH.exists():
        return {"available": False, "message": "No FYERS screener data directory found"}

    screener_files = sorted(
        FYERS_DATA_PATH.glob("screener_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not screener_files:
        return {"available": False, "message": "No screener runs found"}

    latest_file = screener_files[0]
    try:
        payload = json.loads(latest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in {latest_file.name}")

    return {
        "available": True,
        "file": latest_file.name,
        "updated_at": datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat(),
        "data": payload,
    }


@app.get("/api/agents/{signature}/institutional-shadow/latest")
async def get_latest_institutional_shadow(signature: str):
    """Get latest institutional shadow summary from agent trading screener audit log."""
    agent_dir = DATA_PATH / signature
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    screener_log = agent_dir / "trading" / "fyers_screener.jsonl"
    if not screener_log.exists():
        return {
            "available": False,
            "message": "No agent screener audit log found",
            "signature": signature,
        }

    latest_payload = None
    with open(screener_log, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                latest_payload = json.loads(line)
            except json.JSONDecodeError:
                continue

    if not isinstance(latest_payload, dict):
        return {
            "available": False,
            "message": "No valid screener audit entries found",
            "signature": signature,
        }

    shadow = latest_payload.get("institutional_shadow", {})
    return {
        "available": True,
        "signature": signature,
        "timestamp": latest_payload.get("timestamp"),
        "date": latest_payload.get("date"),
        "success": latest_payload.get("success"),
        "institutional_shadow": shadow if isinstance(shadow, dict) else {},
    }


@app.get("/api/agents/{signature}/institutional/decision-cards")
async def get_institutional_decision_cards(signature: str, limit: int = Query(default=20, ge=1, le=200)):
    """Get latest institutional decision cards with reflection fields."""
    agent_dir = DATA_PATH / signature
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    rows = _fetch_institutional_rows(signature=signature, limit=limit)
    return {
        "signature": signature,
        "count": len(rows),
        "cards": rows,
    }


@app.get("/api/agents/{signature}/institutional/monitoring")
async def get_institutional_monitoring(signature: str):
    """Get institutional monitoring summary including priors and alert signals."""
    agent_dir = DATA_PATH / signature
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    rows = _fetch_institutional_rows(signature=signature, limit=200)
    priors = _fetch_strategy_priors(signature=signature)
    alerts = _build_institutional_alerts(rows)

    total = len(rows)
    approved = sum(1 for row in rows if row.get("approved", False))
    vetoed = total - approved
    outcomes = [row.get("pnl_pct") for row in rows if row.get("pnl_pct") is not None]
    avg_pnl = (sum(float(value) for value in outcomes) / len(outcomes)) if outcomes else None

    return {
        "signature": signature,
        "monitoring": {
            "total_decisions": total,
            "approved_decisions": approved,
            "vetoed_decisions": vetoed,
            "veto_rate_pct": round((vetoed / total) * 100, 2) if total else 0.0,
            "avg_realized_pnl_pct": round(avg_pnl, 4) if avg_pnl is not None else None,
        },
        "strategy_priors": priors,
        "alerts": alerts,
    }


@app.get("/api/agents/{signature}/institutional/audit-export")
async def export_institutional_audit(
    signature: str,
    fmt: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """Export institutional audit rows in JSON or CSV format."""
    agent_dir = DATA_PATH / signature
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    rows = _fetch_institutional_rows(signature=signature, limit=limit)

    if fmt == "json":
        return {
            "signature": signature,
            "count": len(rows),
            "rows": rows,
        }

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "experience_id",
            "created_at",
            "symbol",
            "action",
            "confidence",
            "approved",
            "rationale",
            "risk_hard_blocks",
            "outcome_label",
            "pnl_pct",
            "reflection_note",
            "decision_quality",
            "risk_efficiency",
            "timing_quality",
        ],
    )
    writer.writeheader()
    for row in rows:
        csv_row = dict(row)
        csv_row["risk_hard_blocks"] = ";".join(row.get("risk_hard_blocks", []))
        writer.writerow(csv_row)

    filename = f"{signature}_institutional_audit.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


ARTIFACT_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx'}
ARTIFACT_MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}


@app.get("/api/artifacts/random")
async def get_random_artifacts(count: int = Query(default=30, ge=1, le=100)):
    """Get a random sample of agent-produced artifact files"""
    if not DATA_PATH.exists():
        return {"artifacts": []}

    artifacts = []
    for agent_dir in DATA_PATH.iterdir():
        if not agent_dir.is_dir():
            continue
        sandbox_dir = agent_dir / "sandbox"
        if not sandbox_dir.exists():
            continue
        signature = agent_dir.name
        for date_dir in sandbox_dir.iterdir():
            if not date_dir.is_dir():
                continue
            for file_path in date_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                # Skip code_exec, videos, and reference_files directories
                rel_parts = file_path.relative_to(date_dir).parts
                if any(p in ('code_exec', 'videos', 'reference_files') for p in rel_parts):
                    continue
                ext = file_path.suffix.lower()
                if ext not in ARTIFACT_EXTENSIONS:
                    continue
                rel_path = str(file_path.relative_to(DATA_PATH))
                artifacts.append({
                    "agent": signature,
                    "date": date_dir.name,
                    "filename": file_path.name,
                    "extension": ext,
                    "size_bytes": file_path.stat().st_size,
                    "path": rel_path,
                })

    if len(artifacts) > count:
        artifacts = random.sample(artifacts, count)

    return {"artifacts": artifacts}


@app.get("/api/artifacts/file")
async def get_artifact_file(path: str = Query(...)):
    """Serve an artifact file for preview/download"""
    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    file_path = (DATA_PATH / path).resolve()
    # Ensure resolved path is within DATA_PATH
    if not str(file_path).startswith(str(DATA_PATH.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = file_path.suffix.lower()
    media_type = ARTIFACT_MIME_TYPES.get(ext, 'application/octet-stream')
    return FileResponse(file_path, media_type=media_type)


@app.get("/api/settings/hidden-agents")
async def get_hidden_agents():
    """Get list of hidden agent signatures"""
    if HIDDEN_AGENTS_PATH.exists():
        with open(HIDDEN_AGENTS_PATH, 'r') as f:
            hidden = json.load(f)
        return {"hidden": hidden}
    return {"hidden": []}


@app.put("/api/settings/hidden-agents")
async def set_hidden_agents(body: dict):
    """Set list of hidden agent signatures"""
    hidden = body.get("hidden", [])
    HIDDEN_AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HIDDEN_AGENTS_PATH, 'w') as f:
        json.dump(hidden, f)
    return {"status": "ok"}


DISPLAYING_NAMES_PATH = Path(__file__).parent.parent / "data" / "displaying_names.json"

@app.get("/api/settings/displaying-names")
async def get_displaying_names():
    """Get display name mapping {signature: display_name}"""
    if DISPLAYING_NAMES_PATH.exists():
        with open(DISPLAYING_NAMES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to LiveBench real-time updates"
        })

        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Echo back for now, in production this would handle commands
            await websocket.send_json({
                "type": "echo",
                "data": data
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/broadcast")
async def broadcast_message(message: dict):
    """
    Endpoint for LiveBench to broadcast updates to connected clients
    This should be called by the LiveAgent during execution
    """
    await manager.broadcast(message)
    return {"status": "broadcast sent"}


# File watcher for live updates (optional, for when agents are running)
async def watch_agent_files():
    """
    Watch agent data files for changes and broadcast updates
    This runs as a background task
    """
    import time
    last_modified = {}

    while True:
        try:
            if DATA_PATH.exists():
                for agent_dir in DATA_PATH.iterdir():
                    if agent_dir.is_dir():
                        signature = agent_dir.name

                        # Check balance file
                        balance_file = agent_dir / "economic" / "balance.jsonl"
                        if balance_file.exists():
                            mtime = balance_file.stat().st_mtime
                            key = f"{signature}_balance"

                            if key not in last_modified or mtime > last_modified[key]:
                                last_modified[key] = mtime

                                # Read latest balance
                                with open(balance_file, 'r') as f:
                                    lines = f.readlines()
                                    if lines:
                                        data = json.loads(lines[-1])
                                        await manager.broadcast({
                                            "type": "balance_update",
                                            "signature": signature,
                                            "data": data
                                        })

                        # Check decisions file
                        decision_file = agent_dir / "decisions" / "decisions.jsonl"
                        if decision_file.exists():
                            mtime = decision_file.stat().st_mtime
                            key = f"{signature}_decision"

                            if key not in last_modified or mtime > last_modified[key]:
                                last_modified[key] = mtime

                                # Read latest decision
                                with open(decision_file, 'r') as f:
                                    lines = f.readlines()
                                    if lines:
                                        data = json.loads(lines[-1])
                                        await manager.broadcast({
                                            "type": "activity_update",
                                            "signature": signature,
                                            "data": data
                                        })
        except Exception as e:
            print(f"Error watching files: {e}")

        await asyncio.sleep(1)  # Check every second


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    asyncio.create_task(watch_agent_files())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
