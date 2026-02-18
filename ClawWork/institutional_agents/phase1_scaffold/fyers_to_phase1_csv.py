from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


IST = timezone(timedelta(hours=5, minutes=30))


def _load_env_file(path: Path) -> List[str]:
    loaded: List[str] = []
    if not path.exists() or not path.is_file():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


@dataclass
class ExportRow:
    timestamp: str
    underlying: str
    ltp: float
    prev_close: float
    session: str
    daily_realized_pnl_pct: float
    bid_ask_spread_bps: float


class FyersHistoryClient:
    def __init__(self) -> None:
        self.api_base_url = (os.getenv("FYERS_API_BASE_URL") or "https://api-t1.fyers.in/api/v3").rstrip("/")
        self.api_root_url = self._derive_api_root(self.api_base_url)
        self.access_token = (os.getenv("FYERS_ACCESS_TOKEN") or "").strip()
        self.app_id = (os.getenv("FYERS_APP_ID") or os.getenv("FYERS_CLIENT_ID") or "").strip()
        self.auth_header = (os.getenv("FYERS_AUTH_HEADER") or "").strip()
        self.timeout_seconds = float(os.getenv("FYERS_TIMEOUT_SECONDS", "30"))

    @staticmethod
    def _derive_api_root(base_url: str) -> str:
        for marker in ("/api/v3", "/api/v2", "/api"):
            if marker in base_url:
                return base_url.split(marker, 1)[0].rstrip("/")
        return base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.auth_header:
            headers["Authorization"] = self.auth_header
        elif self.access_token and self.app_id:
            headers["Authorization"] = f"{self.app_id}:{self.access_token}"
        elif self.access_token:
            token = self.access_token
            if not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            headers["Authorization"] = token
        return headers

    def _request(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.access_token:
            return {
                "success": False,
                "error": "FYERS_ACCESS_TOKEN is not set",
                "message": "Set FYERS_ACCESS_TOKEN in environment before running exporter",
            }

        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{self.api_base_url}/{path.lstrip('/')}"

        try:
            response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            return {"success": False, "url": url, "error": f"Request failed: {exc}"}

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        ok = 200 <= response.status_code < 300
        s_field = str(body.get("s", "")).lower() if isinstance(body, dict) else ""
        success = ok and s_field not in {"error", "failed", "fail"}
        return {
            "success": success,
            "url": url,
            "status_code": response.status_code,
            "data": body,
            "error": None if success else self._extract_error(body),
        }

    @staticmethod
    def _extract_error(body: Any) -> str:
        if isinstance(body, dict):
            for key in ("message", "error", "reason"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            return json.dumps(body)
        return str(body)

    def history(self, symbol: str, resolution: str, range_from: str, range_to: str) -> Dict[str, Any]:
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1",
        }
        attempts = [
            "/history",
            "/data/history",
            f"{self.api_root_url}/history",
            f"{self.api_root_url}/data/history",
        ]
        errors: List[Dict[str, Any]] = []
        for path in attempts:
            result = self._request(path, params=params)
            if result.get("success"):
                result["history_endpoint_used"] = path
                return result
            errors.append(
                {
                    "endpoint": path,
                    "status_code": result.get("status_code"),
                    "error": result.get("error"),
                    "url": result.get("url"),
                }
            )
        return {"success": False, "error": "All history endpoint attempts failed", "attempts": errors}


def _resolve_symbol_map() -> Dict[str, str]:
    return {
        "NIFTY50": os.getenv("FYERS_INDEX_SYMBOL_NIFTY50", "NSE:NIFTY50-INDEX"),
        "BANKNIFTY": os.getenv("FYERS_INDEX_SYMBOL_BANKNIFTY", "NSE:NIFTYBANK-INDEX"),
        "SENSEX": os.getenv("FYERS_INDEX_SYMBOL_SENSEX", "BSE:SENSEX-INDEX"),
    }


def _parse_candles(payload: Dict[str, Any]) -> List[List[Any]]:
    data = payload.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("candles"), list):
        return data["candles"]
    if isinstance(payload.get("candles"), list):
        return payload["candles"]
    return []


def _epoch_to_ist(ts_value: Any) -> datetime:
    ts_float = float(ts_value)
    if ts_float > 1_000_000_000_000:
        ts_float /= 1000.0
    return datetime.fromtimestamp(ts_float, tz=timezone.utc).astimezone(IST)


def _session_for_timestamp(dt_obj: datetime, resolution: str) -> str:
    if resolution.upper() in {"D", "1D"}:
        return "CLOSE"
    local_time = dt_obj.timetz().replace(tzinfo=None)
    if local_time < time(10, 30):
        return "OPEN"
    if local_time < time(14, 0):
        return "MIDDAY"
    return "CLOSE"


def _normalize_timestamp(dt_obj: datetime, resolution: str) -> datetime:
    if resolution.upper() in {"D", "1D"}:
        return dt_obj.replace(hour=15, minute=20, second=0, microsecond=0)
    return dt_obj.replace(second=0, microsecond=0)


def _build_rows(
    underlying: str,
    candles: List[List[Any]],
    resolution: str,
    daily_realized_pnl_pct: float,
    spread_bps: float,
) -> List[ExportRow]:
    rows: List[ExportRow] = []
    prev_close_value: Optional[float] = None

    for candle in candles:
        if not isinstance(candle, list) or len(candle) < 5:
            continue
        dt_obj = _normalize_timestamp(_epoch_to_ist(candle[0]), resolution)
        open_px = float(candle[1])
        close_px = float(candle[4])
        prev_close = prev_close_value if prev_close_value is not None else open_px
        session = _session_for_timestamp(dt_obj, resolution)

        rows.append(
            ExportRow(
                timestamp=dt_obj.isoformat(),
                underlying=underlying,
                ltp=round(close_px, 4),
                prev_close=round(prev_close, 4),
                session=session,
                daily_realized_pnl_pct=round(daily_realized_pnl_pct, 4),
                bid_ask_spread_bps=round(spread_bps, 4),
            )
        )
        prev_close_value = close_px

    return rows


def _write_csv(path: Path, rows: List[ExportRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "underlying",
        "ltp",
        "prev_close",
        "session",
        "daily_realized_pnl_pct",
        "bid_ask_spread_bps",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "timestamp": row.timestamp,
                "underlying": row.underlying,
                "ltp": row.ltp,
                "prev_close": row.prev_close,
                "session": row.session,
                "daily_realized_pnl_pct": row.daily_realized_pnl_pct,
                "bid_ask_spread_bps": row.bid_ask_spread_bps,
            })


def main() -> int:
    parser = argparse.ArgumentParser(description="Export FYERS historical candles to Phase 1 CSV format")
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional .env path. Defaults to ClawWork/.env when available.",
    )
    parser.add_argument("--from-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--resolution", default="D", help="FYERS resolution, e.g. D, 60, 15")
    parser.add_argument(
        "--underlyings",
        default="NIFTY50,BANKNIFTY,SENSEX",
        help="Comma-separated underlyings from {NIFTY50,BANKNIFTY,SENSEX}",
    )
    parser.add_argument("--daily-realized-pnl-pct", type=float, default=0.0)
    parser.add_argument("--spread-bps", type=float, default=25.0)
    parser.add_argument("--min-rows", type=int, default=20)
    parser.add_argument("--out-csv", default="sample_batch_input_real_fyers.csv")
    args = parser.parse_args()

    default_env_file = Path(__file__).resolve().parents[2] / ".env"
    env_file = Path(args.env_file).expanduser().resolve() if args.env_file else default_env_file
    loaded_env_keys = _load_env_file(env_file)

    symbol_map = _resolve_symbol_map()
    selected = [item.strip().upper() for item in args.underlyings.split(",") if item.strip()]
    invalid = [name for name in selected if name not in symbol_map]
    if invalid:
        print(json.dumps({"success": False, "error": f"Invalid underlyings: {invalid}"}, indent=2))
        return 2

    client = FyersHistoryClient()
    all_rows: List[ExportRow] = []
    endpoint_usage: Dict[str, str] = {}
    fetch_errors: Dict[str, Any] = {}

    for underlying in selected:
        symbol = symbol_map[underlying]
        result = client.history(
            symbol=symbol,
            resolution=args.resolution,
            range_from=args.from_date,
            range_to=args.to_date,
        )
        if not result.get("success"):
            fetch_errors[underlying] = result
            continue

        endpoint_usage[underlying] = str(result.get("history_endpoint_used", ""))
        candles = _parse_candles(result)
        rows = _build_rows(
            underlying=underlying,
            candles=candles,
            resolution=args.resolution,
            daily_realized_pnl_pct=args.daily_realized_pnl_pct,
            spread_bps=args.spread_bps,
        )
        all_rows.extend(rows)

    all_rows.sort(key=lambda row: row.timestamp)

    out_path = Path(args.out_csv)
    if all_rows:
        _write_csv(out_path, all_rows)

    covered_dates = sorted({row.timestamp[:10] for row in all_rows})
    payload = {
        "success": len(fetch_errors) == 0 and len(all_rows) >= args.min_rows,
        "output_csv": str(out_path),
        "env_file_used": str(env_file) if env_file.exists() else None,
        "env_keys_loaded_count": len(loaded_env_keys),
        "fyers_access_token_present": bool(os.getenv("FYERS_ACCESS_TOKEN")),
        "fyers_app_id_present": bool(os.getenv("FYERS_APP_ID") or os.getenv("FYERS_CLIENT_ID")),
        "requested_underlyings": selected,
        "rows": len(all_rows),
        "min_rows_required": args.min_rows,
        "covered_trading_days": len(covered_dates),
        "window": {"from": args.from_date, "to": args.to_date},
        "resolution": args.resolution,
        "history_endpoint_used": endpoint_usage,
        "errors": fetch_errors,
    }
    print(json.dumps(payload, indent=2))

    if fetch_errors:
        return 2
    return 0 if len(all_rows) >= args.min_rows else 3


if __name__ == "__main__":
    raise SystemExit(main())
