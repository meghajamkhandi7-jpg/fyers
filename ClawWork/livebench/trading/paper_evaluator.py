from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _extract_market_return_pct(row: Dict[str, Any]) -> float:
    candidates = ["market_return_pct", "next_return_pct", "return_pct", "price_change_pct"]
    for key in candidates:
        if key in row:
            return float(row[key])
    return 0.0


def _normalize_action(value: Any) -> str:
    return str(value or "NO_TRADE").strip().upper()


def _row_net_return_pct(row: Dict[str, Any], *, transaction_cost_bps: float, slippage_bps: float) -> float:
    action = _normalize_action(row.get("action"))
    market_return_pct = _extract_market_return_pct(row)

    gross_pct = 0.0
    traded = action in {"BUY_CALL", "BUY_PUT"}

    if action == "BUY_CALL":
        gross_pct = market_return_pct
    elif action == "BUY_PUT":
        gross_pct = -market_return_pct

    if traded:
        total_execution_cost_pct = (float(transaction_cost_bps) + float(slippage_bps)) * 0.01
    else:
        total_execution_cost_pct = 0.0

    return gross_pct - total_execution_cost_pct


def _max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = _safe_div(peak - equity, peak)
        if drawdown > max_dd:
            max_dd = drawdown
    return max_dd


def run_paper_backtest(
    rows: List[Dict[str, Any]],
    *,
    transaction_cost_bps: float = 5.0,
    slippage_bps: float = 5.0,
    annualization_factor: int = 252,
) -> Dict[str, Any]:
    if annualization_factor <= 0:
        raise ValueError("annualization_factor must be > 0")

    if not isinstance(rows, list):
        raise ValueError("rows must be a list")

    period_returns_decimal: List[float] = []
    trade_returns_decimal: List[float] = []
    equity_curve: List[float] = [1.0]

    buy_call_count = 0
    buy_put_count = 0
    no_trade_count = 0

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each row must be an object")

        action = _normalize_action(row.get("action"))
        if action == "BUY_CALL":
            buy_call_count += 1
        elif action == "BUY_PUT":
            buy_put_count += 1
        else:
            no_trade_count += 1

        net_return_pct = _row_net_return_pct(
            row,
            transaction_cost_bps=transaction_cost_bps,
            slippage_bps=slippage_bps,
        )
        net_return_decimal = net_return_pct / 100.0

        period_returns_decimal.append(net_return_decimal)

        if action in {"BUY_CALL", "BUY_PUT"}:
            trade_returns_decimal.append(net_return_decimal)

        equity_curve.append(equity_curve[-1] * (1.0 + net_return_decimal))

    total_periods = len(rows)
    total_trades = buy_call_count + buy_put_count

    cumulative_return = equity_curve[-1] - 1.0
    avg_period_return = mean(period_returns_decimal) if period_returns_decimal else 0.0
    period_vol = pstdev(period_returns_decimal) if len(period_returns_decimal) > 1 else 0.0

    if period_vol > 0:
        sharpe = (avg_period_return / period_vol) * math.sqrt(annualization_factor)
    else:
        sharpe = 0.0

    downside = [value for value in period_returns_decimal if value < 0]
    downside_vol = pstdev(downside) if len(downside) > 1 else 0.0
    if downside_vol > 0:
        sortino = (avg_period_return / downside_vol) * math.sqrt(annualization_factor)
    else:
        sortino = 0.0

    profitable_trades = sum(1 for value in trade_returns_decimal if value > 0)
    hit_rate = _safe_div(profitable_trades, total_trades)
    turnover = _safe_div(total_trades, total_periods)
    max_drawdown = _max_drawdown(equity_curve)

    return {
        "summary": {
            "total_periods": total_periods,
            "total_trades": total_trades,
            "buy_call_count": buy_call_count,
            "buy_put_count": buy_put_count,
            "no_trade_count": no_trade_count,
        },
        "performance": {
            "cumulative_return_pct": round(cumulative_return * 100.0, 4),
            "sharpe": round(sharpe, 4),
            "sortino": round(sortino, 4),
            "max_drawdown_pct": round(max_drawdown * 100.0, 4),
            "hit_rate_pct": round(hit_rate * 100.0, 4),
            "turnover_pct": round(turnover * 100.0, 4),
        },
        "assumptions": {
            "transaction_cost_bps": float(transaction_cost_bps),
            "slippage_bps": float(slippage_bps),
            "annualization_factor": int(annualization_factor),
        },
    }


def compare_backtests(
    candidate_rows: List[Dict[str, Any]],
    baseline_rows: Optional[List[Dict[str, Any]]] = None,
    *,
    transaction_cost_bps: float = 5.0,
    slippage_bps: float = 5.0,
    annualization_factor: int = 252,
) -> Dict[str, Any]:
    candidate = run_paper_backtest(
        candidate_rows,
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        annualization_factor=annualization_factor,
    )

    if baseline_rows is None:
        return {
            "candidate": candidate,
            "baseline": None,
            "delta": None,
        }

    baseline = run_paper_backtest(
        baseline_rows,
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        annualization_factor=annualization_factor,
    )

    delta = {
        "cumulative_return_pct": round(
            candidate["performance"]["cumulative_return_pct"] - baseline["performance"]["cumulative_return_pct"],
            4,
        ),
        "sharpe": round(candidate["performance"]["sharpe"] - baseline["performance"]["sharpe"], 4),
        "max_drawdown_pct": round(
            candidate["performance"]["max_drawdown_pct"] - baseline["performance"]["max_drawdown_pct"],
            4,
        ),
        "hit_rate_pct": round(
            candidate["performance"]["hit_rate_pct"] - baseline["performance"]["hit_rate_pct"],
            4,
        ),
    }

    return {
        "candidate": candidate,
        "baseline": baseline,
        "delta": delta,
    }
