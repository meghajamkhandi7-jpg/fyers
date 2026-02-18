# ClawWork + FYERS Execution Guide (Step-by-Step)

This guide helps you bring the tool up from scratch and run it safely in **dry-run mode**.

---

## 1) Prerequisites

- Python dependencies installed
- Node.js installed (for dashboard frontend)
- FYERS app credentials available

From project root:

```bash
cd /workspaces/fyers/ClawWork
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

---

## 2) Configure environment

Copy example env if needed:

```bash
cp .env.example .env
```

Set these FYERS values in `.env`:

- `FYERS_APP_ID`
- `FYERS_APP_SECRET` (or `FYERS_SECRET_KEY`)
- `FYERS_REDIRECT_URI`

Keep safe mode enabled:

```dotenv
FYERS_DRY_RUN=true
FYERS_ALLOW_LIVE_ORDERS=false
```

Set your watchlist (Indian symbols):

```dotenv
FYERS_WATCHLIST=NSE:RELIANCE-EQ,NSE:TCS-EQ,NSE:HDFCBANK-EQ,NSE:INFY-EQ,NSE:SBIN-EQ
```

---

## 3) Generate/refresh FYERS access token

```bash
cd /workspaces/fyers/ClawWork
bash ./scripts/fyers_token.sh
```

This updates `FYERS_ACCESS_TOKEN` in `.env`.

---

## 4) Validate FYERS connection

```bash
cd /workspaces/fyers/ClawWork
bash ./scripts/fyers_healthcheck.sh
```

Expected: `FYERS health check passed`.

---

## 5) Start dashboard

Use terminal 1:

```bash
cd /workspaces/fyers/ClawWork
bash ./start_dashboard.sh
```

Access:

- Dashboard: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

> If you are in Codespaces, use the forwarded 3000/8000 URLs.

---

## 6) Run agent session (optional for LiveBench data)

Use terminal 2:

```bash
cd /workspaces/fyers/ClawWork
bash ./run_test_agent.sh
```

The script auto-falls back to inline tasks if GDPVal parquet is missing.

---

## 7) Run stock screener

Use terminal 3:

```bash
cd /workspaces/fyers/ClawWork
bash ./scripts/fyers_screener.sh
```

Expected output includes:

- `BUY_CANDIDATE`
- `WATCH`
- `AVOID`

and saves a JSON result in:

`livebench/data/fyers/`

---

## 8) Verify results

### A) Dashboard

- Open **Dashboard** page
- Check **Latest FYERS Screener** panel
- It auto-refreshes every ~15 seconds

### B) Files

- Latest screener JSON: `livebench/data/fyers/screener_*.json`
- Agent-level screener logs (tool-based runs):
  `livebench/data/agent_data/<signature>/trading/fyers_screener.jsonl`
- Dry-run order audit logs:
  `livebench/data/agent_data/<signature>/trading/fyers_orders.jsonl`

---

## 9) Daily usage routine (recommended)

1. `bash ./scripts/fyers_token.sh`
2. `bash ./scripts/fyers_healthcheck.sh`
3. `bash ./scripts/fyers_screener.sh`
4. Review Dashboard panel + saved JSON

---

## 10) Safety notes

- You are currently in **dry-run only** mode.
- No live orders are sent while:
  - `FYERS_DRY_RUN=true`
  - `FYERS_ALLOW_LIVE_ORDERS=false`

Do not change these unless you intentionally want live trading.

---

## 11) Troubleshooting

### `EnvironmentNameNotFound: livebench`

`run_test_agent.sh` now continues with current environment. You can still run it.

### `404 page not found` in screener

Client now tries multiple FYERS quote endpoints automatically. Re-run screener.

### `invalid app id hash`

Re-run token script and verify app secret value from FYERS app settings.

### `Exit code 127` when starting dashboard

Use full command with `cd`:

```bash
cd /workspaces/fyers/ClawWork && bash ./start_dashboard.sh
```
