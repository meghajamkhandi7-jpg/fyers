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

You can also provide company-name style entries (for example `NSE:Reliance Industries-EQ`);
the screener now auto-normalizes common names to FYERS tradable symbols.

Optional: add custom alias overrides in `.env` (JSON object):

```dotenv
FYERS_WATCHLIST_ALIASES={"Reliance Industries":"RELIANCE","Larsen & Toubro":"LT"}
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

This now starts backend + frontend + FYERS screener loop together.

Optional controls:

```bash
cd /workspaces/fyers/ClawWork
SCREENER_INTERVAL_SECONDS=60 bash ./start_dashboard.sh
```

```bash
cd /workspaces/fyers/ClawWork
SCREENER_ENABLED=0 bash ./start_dashboard.sh
```

Access:

- Dashboard: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`


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

Use this only for manual one-off runs (the dashboard startup already runs it in a loop).

If any requested symbols do not return quote rows, the script now prints a `Warnings` section
and includes `missing_quote_symbols` in the saved JSON.

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

### `Incorrect API key provided` when running `run_test_agent.sh`

Your `.env` still contains placeholder values (for example `your-api-key-here`).

Set real values for at least:

- `OPENAI_API_KEY`
- `WEB_SEARCH_API_KEY`

If `EVALUATION_API_KEY` is set, it must also be real (or unset it to fall back to `OPENAI_API_KEY`).

### `E2B sandbox 401 Unauthorized` during wrap-up

If `E2B_API_KEY` is missing/placeholder, `run_test_agent.sh` now auto-disables wrap-up for that run.
To enable wrap-up artifact recovery, set a valid `E2B_API_KEY` in `.env`.

### `template 'gdpval-workspace' not found` in E2B

Your E2B account does not have that template alias.

Runtime now tries these in order:

1. `E2B_TEMPLATE_ID` (if set)
2. `E2B_TEMPLATE_ALIAS` / `E2B_TEMPLATE` (if set)
3. legacy alias `gdpval-workspace`
4. E2B default template

If you built a custom template, add one of these to `.env`:

```dotenv
E2B_TEMPLATE_ID=tpl_xxxxxxxxxxxxx
# or
E2B_TEMPLATE_ALIAS=gdpval-workspace
```

### `Error code: 429` / `You exceeded your current quota`

This is a provider quota/billing limit (not a code crash).

`run_test_agent.sh` now performs an API preflight check and exits early if quota is exhausted.

Fix options:

- Add billing/credits for the key in use.
- Switch to another provider/key via `OPENAI_API_BASE` + `OPENAI_API_KEY`.
- Use a lower-cost model in config (for example `gpt-4o-mini`).

Optional: skip preflight with `LIVEBENCH_SKIP_API_PREFLIGHT=1` if you need to debug other parts.

### `No meta-prompt found for occupation ...`

Some inline/demo occupations may not have an exact file in `eval/meta_prompts/`.

Evaluator now falls back automatically to the closest available rubric (mapped or nearest match), so runs continue instead of failing `submit_work`.

If you want strict category matching, add a dedicated JSON rubric file under:

`eval/meta_prompts/<Occupation_Name>.json`
