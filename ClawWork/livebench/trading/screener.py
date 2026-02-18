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
    index_neutral_pct: float = 0.25
    index_strong_trend_pct: float = 0.8


DEFAULT_INDEX_SYMBOLS: Dict[str, str] = {
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}


DEFAULT_STRIKE_STEPS: Dict[str, int] = {
    "NIFTY50": 50,
    "BANKNIFTY": 100,
    "SENSEX": 100,
}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
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
        index_neutral_pct=_env_float("FYERS_INDEX_NEUTRAL_PCT", 0.25),
        index_strong_trend_pct=_env_float("FYERS_INDEX_STRONG_TREND_PCT", 0.8),
    )


def load_index_symbols() -> Dict[str, str]:
    mapping = dict(DEFAULT_INDEX_SYMBOLS)
    mapping["NIFTY50"] = os.getenv("FYERS_INDEX_SYMBOL_NIFTY50", mapping["NIFTY50"])
    mapping["BANKNIFTY"] = os.getenv("FYERS_INDEX_SYMBOL_BANKNIFTY", mapping["BANKNIFTY"])
    mapping["SENSEX"] = os.getenv("FYERS_INDEX_SYMBOL_SENSEX", mapping["SENSEX"])
    return mapping


def load_strike_steps() -> Dict[str, int]:
    return {
        "NIFTY50": _env_int("FYERS_STRIKE_STEP_NIFTY50", DEFAULT_STRIKE_STEPS["NIFTY50"]),
        "BANKNIFTY": _env_int("FYERS_STRIKE_STEP_BANKNIFTY", DEFAULT_STRIKE_STEPS["BANKNIFTY"]),
        "SENSEX": _env_int("FYERS_STRIKE_STEP_SENSEX", DEFAULT_STRIKE_STEPS["SENSEX"]),
    }


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


def _round_to_step(value: float, step: int) -> int:
    if step <= 0:
        return int(round(value))
    return int(round(value / step) * step)


def _pick_preferred_moneyness(abs_change_pct: float, strong_trend_pct: float, neutral_pct: float) -> str:
    if abs_change_pct >= strong_trend_pct:
        return "ATM_OR_1_OTM"
    if abs_change_pct >= neutral_pct:
        return "ATM"
    return "ATM_OR_1_ITM"


def _build_strike_suggestions(
    index_name: str,
    index_ltp: float,
    index_change_pct: float,
    strike_step: int,
    config: ScreenerConfig,
) -> Dict[str, Any]:
    abs_change = abs(index_change_pct)
    if index_change_pct >= config.index_neutral_pct:
        side = "CE"
        directional_bias = "BULLISH"
    elif index_change_pct <= -config.index_neutral_pct:
        side = "PE"
        directional_bias = "BEARISH"
    else:
        side = "NO_TRADE"
        directional_bias = "NEUTRAL"

    atm = _round_to_step(index_ltp, strike_step)
    preferred_moneyness = _pick_preferred_moneyness(abs_change, config.index_strong_trend_pct, config.index_neutral_pct)

    if side == "NO_TRADE":
        preferred_strike = None
        candidates = []
        reason = (
            f"{index_name} is range-bound ({index_change_pct:.2f}%). "
            f"Wait for breakout beyond ±{config.index_neutral_pct:.2f}%"
        )
        confidence = 35
    else:
        one_step_otm = atm + strike_step if side == "CE" else atm - strike_step
        one_step_itm = atm - strike_step if side == "CE" else atm + strike_step

        if preferred_moneyness == "ATM_OR_1_OTM":
            preferred_strike = one_step_otm
        elif preferred_moneyness == "ATM":
            preferred_strike = atm
        else:
            preferred_strike = one_step_itm

        candidates = [
            {"label": "1_ITM", "strike": int(one_step_itm)},
            {"label": "ATM", "strike": int(atm)},
            {"label": "1_OTM", "strike": int(one_step_otm)},
        ]
        reason = (
            f"{index_name} shows {directional_bias.lower()} momentum ({index_change_pct:.2f}%). "
            f"Preferred setup: {preferred_moneyness}"
        )
        confidence = int(max(40, min(90, 45 + abs_change * 20)))

    return {
        "index": index_name,
        "signal": directional_bias,
        "option_side": side,
        "ltp": index_ltp,
        "change_pct": index_change_pct,
        "strike_step": strike_step,
        "atm_strike": int(atm),
        "preferred_moneyness": preferred_moneyness,
        "preferred_strike": int(preferred_strike) if preferred_strike is not None else None,
        "candidate_strikes": candidates,
        "confidence": confidence,
        "reason": reason,
    }


def build_index_recommendations(client: Any, config: ScreenerConfig) -> Dict[str, Any]:
    symbols_map = load_index_symbols()
    strike_steps = load_strike_steps()
    ordered_names = ["NIFTY50", "BANKNIFTY", "SENSEX"]

    symbols_csv = ",".join(symbols_map[name] for name in ordered_names if symbols_map.get(name))
    quote_response = client.quotes(symbols_csv)
    if not quote_response.get("success"):
        return {
            "success": False,
            "error": quote_response.get("error", "Index quote request failed"),
            "quotes_response": quote_response,
            "results": [],
            "summary": {"tracked": 0, "bullish": 0, "bearish": 0, "neutral": 0},
        }

    rows = normalize_quote_rows(quote_response)
    by_symbol = {row.get("symbol"): row for row in rows}
    recommendations: List[Dict[str, Any]] = []

    for name in ordered_names:
        symbol = symbols_map.get(name)
        row = by_symbol.get(symbol)
        if not row:
            continue

        ltp = row.get("last_price")
        change_pct = row.get("change_pct")
        if ltp is None or change_pct is None:
            continue

        recommendations.append(
            _build_strike_suggestions(
                index_name=name,
                index_ltp=ltp,
                index_change_pct=change_pct,
                strike_step=strike_steps.get(name, DEFAULT_STRIKE_STEPS.get(name, 100)),
                config=config,
            )
        )

    summary = {
        "tracked": len(recommendations),
        "bullish": len([r for r in recommendations if r.get("signal") == "BULLISH"]),
        "bearish": len([r for r in recommendations if r.get("signal") == "BEARISH"]),
        "neutral": len([r for r in recommendations if r.get("signal") == "NEUTRAL"]),
    }

    return {
        "success": True,
        "symbols": symbols_map,
        "summary": summary,
        "results": recommendations,
        "thresholds": {
            "neutral_pct": config.index_neutral_pct,
            "strong_trend_pct": config.index_strong_trend_pct,
        },
    }


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
    index_recommendations = build_index_recommendations(client=client, config=config)

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
        "index_recommendations": index_recommendations.get("results", []),
        "index_summary": index_recommendations.get("summary", {}),
        "index_thresholds": index_recommendations.get("thresholds", {}),
        "index_symbols": index_recommendations.get("symbols", {}),
        "index_error": None if index_recommendations.get("success") else index_recommendations.get("error"),
        "message": f"Screener completed: {len(buy_candidates)} buy candidate(s), {len(watch)} watch, {len(avoid)} avoid",
    }
