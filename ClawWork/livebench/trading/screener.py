"""FYERS watchlist screener and beginner strategy helpers."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ScreenerConfig:
    buy_min_pct: float = 0.3
    buy_max_pct: float = 2.5
    avoid_drawdown_pct: float = -2.0
    default_capital: float = 5000.0
    risk_pct: float = 1.0
    stop_loss_pct: float = 1.0
    target_pct: float = 2.0


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_screener_config() -> ScreenerConfig:
    return ScreenerConfig(
        buy_min_pct=_env_float("FYERS_SCREENER_BUY_MIN_PCT", 0.3),
        buy_max_pct=_env_float("FYERS_SCREENER_BUY_MAX_PCT", 2.5),
        avoid_drawdown_pct=_env_float("FYERS_SCREENER_AVOID_MAX_DRAWDOWN_PCT", -2.0),
        default_capital=_env_float("FYERS_SCREENER_DEFAULT_CAPITAL", 5000.0),
        risk_pct=_env_float("FYERS_SCREENER_RISK_PCT", 1.0),
        stop_loss_pct=_env_float("FYERS_SCREENER_STOP_LOSS_PCT", 1.0),
        target_pct=_env_float("FYERS_SCREENER_TARGET_PCT", 2.0),
    )


def parse_watchlist(watchlist: str | List[str] | None = None) -> List[str]:
    if isinstance(watchlist, list):
        symbols = [str(item).strip() for item in watchlist if str(item).strip()]
        return list(dict.fromkeys(symbols))

    if isinstance(watchlist, str) and watchlist.strip():
        text = watchlist.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parse_watchlist(parsed)
            except json.JSONDecodeError:
                pass
        symbols = [chunk.strip() for chunk in text.split(",") if chunk.strip()]
        return list(dict.fromkeys(symbols))

    env_watchlist = os.getenv("FYERS_WATCHLIST", "")
    if not env_watchlist.strip():
        return []

    symbols = [chunk.strip() for chunk in env_watchlist.split(",") if chunk.strip()]
    return list(dict.fromkeys(symbols))


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _get_number(mapping: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        if key in mapping:
            out = _to_float(mapping.get(key))
            if out is not None:
                return out
    return None


def normalize_quote_rows(quote_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = quote_response.get("data", {}) if isinstance(quote_response, dict) else {}
    raw_rows = payload.get("d", []) if isinstance(payload, dict) else []
    rows: List[Dict[str, Any]] = []

    if not isinstance(raw_rows, list):
        return rows

    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        symbol = item.get("n") or item.get("symbol") or item.get("name")
        details = item.get("v", {}) if isinstance(item.get("v"), dict) else item

        last_price = _get_number(details, ["lp", "ltp", "last_price", "lastPrice", "c"])
        prev_close = _get_number(details, ["prev_close_price", "prev_close", "prevClose", "pc", "close_price"])
        change_pct = _get_number(details, ["chp", "change_pct", "pChange", "changePercent"])
        volume = _get_number(details, ["volume", "vol", "v", "ttv"])  # best effort

        if change_pct is None and last_price is not None and prev_close and prev_close != 0:
            change_pct = ((last_price - prev_close) / prev_close) * 100.0

        rows.append(
            {
                "symbol": symbol,
                "last_price": last_price,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "volume": volume,
            }
        )

    return rows


def _build_order_preview(symbol: str, last_price: float, config: ScreenerConfig) -> Dict[str, Any]:
    risk_amount = max(config.default_capital * (config.risk_pct / 100.0), 1.0)
    stop_distance = max(last_price * (config.stop_loss_pct / 100.0), 0.01)
    quantity = max(int(risk_amount / stop_distance), 1)
    stop_loss = round(last_price * (1 - config.stop_loss_pct / 100.0), 2)
    target = round(last_price * (1 + config.target_pct / 100.0), 2)

    return {
        "symbol": symbol,
        "qty": quantity,
        "type": 2,
        "side": 1,
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "stop_loss_level": stop_loss,
        "target_level": target,
        "orderTag": "dryrun_screener",
    }


def evaluate_symbols(rows: List[Dict[str, Any]], config: ScreenerConfig) -> List[Dict[str, Any]]:
    evaluated: List[Dict[str, Any]] = []

    for row in rows:
        symbol = row.get("symbol")
        last_price = row.get("last_price")
        change_pct = row.get("change_pct")

        signal = "WATCH"
        reason = "No trigger"
        order_preview = None

        if not symbol or last_price is None or last_price <= 0:
            signal = "WATCH"
            reason = "Insufficient quote data"
        elif change_pct is None:
            signal = "WATCH"
            reason = "Change % unavailable"
        elif change_pct <= config.avoid_drawdown_pct:
            signal = "AVOID"
            reason = f"Weak momentum ({change_pct:.2f}% <= {config.avoid_drawdown_pct:.2f}%)"
        elif config.buy_min_pct <= change_pct <= config.buy_max_pct:
            signal = "BUY_CANDIDATE"
            reason = (
                f"Momentum in buy zone ({change_pct:.2f}% between "
                f"{config.buy_min_pct:.2f}% and {config.buy_max_pct:.2f}%)"
            )
            order_preview = _build_order_preview(symbol=symbol, last_price=last_price, config=config)
        elif change_pct > config.buy_max_pct:
            signal = "WATCH"
            reason = f"Extended move ({change_pct:.2f}% > {config.buy_max_pct:.2f}%)"
        else:
            signal = "WATCH"
            reason = f"Below momentum threshold ({change_pct:.2f}% < {config.buy_min_pct:.2f}%)"

        evaluated.append(
            {
                **row,
                "signal": signal,
                "reason": reason,
                "order_preview": order_preview,
            }
        )

    return evaluated


def run_screener(client: Any, watchlist: str | List[str] | None = None) -> Dict[str, Any]:
    symbols = parse_watchlist(watchlist)
    if not symbols:
        return {
            "success": False,
            "error": "No watchlist symbols provided",
            "message": "Set FYERS_WATCHLIST in .env or pass watchlist argument",
        }

    symbols_csv = ",".join(symbols)
    quote_response = client.quotes(symbols_csv)
    if not quote_response.get("success"):
        return {
            "success": False,
            "error": quote_response.get("error", "Quote request failed"),
            "quotes_response": quote_response,
        }

    config = load_screener_config()
    rows = normalize_quote_rows(quote_response)
    evaluated = evaluate_symbols(rows, config)

    buy_candidates = [item for item in evaluated if item.get("signal") == "BUY_CANDIDATE"]
    avoid = [item for item in evaluated if item.get("signal") == "AVOID"]
    watch = [item for item in evaluated if item.get("signal") == "WATCH"]

    return {
        "success": True,
        "watchlist": symbols,
        "summary": {
            "total": len(evaluated),
            "buy_candidates": len(buy_candidates),
            "watch": len(watch),
            "avoid": len(avoid),
        },
        "config": asdict(config),
        "results": evaluated,
        "message": f"Screener completed: {len(buy_candidates)} buy candidate(s), {len(watch)} watch, {len(avoid)} avoid",
    }
