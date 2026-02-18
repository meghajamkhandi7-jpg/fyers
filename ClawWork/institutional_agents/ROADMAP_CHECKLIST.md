# Institutional Agents: MVP → Advanced Checklist

Goal: Build an institutional-grade decision system in phases **without changing current production flow**.

## Phase 0 Starter Pack (Created)
- [ ] Review [PHASE0_INPUT_OUTPUT_SCHEMA.md](PHASE0_INPUT_OUTPUT_SCHEMA.md)
- [ ] Review [PHASE0_RISK_POLICY.md](PHASE0_RISK_POLICY.md)
- [ ] Review [PHASE0_ACCEPTANCE_METRICS.md](PHASE0_ACCEPTANCE_METRICS.md)
- [ ] Run sign-off meeting with [PHASE0_SIGNOFF_CHECKLIST.md](PHASE0_SIGNOFF_CHECKLIST.md)

## Working Rules
- [ ] Keep all new work isolated under `institutional_agents/`
- [ ] Do not edit live decision paths until a phase is fully validated
- [ ] Use feature flags before any integration
- [ ] Record every experiment result in a run log

---

## Phase 0 — Foundation (1–3 days)
- [ ] Define target markets: NIFTY50, BANKNIFTY, SENSEX
- [ ] Define instruments: spot/index options/futures (scope for MVP)
- [ ] Define decision outputs: `BUY_CALL`, `BUY_PUT`, `NO_TRADE`, confidence, rationale
- [ ] Define risk outputs: stop loss %, target %, max loss/day
- [ ] Finalize acceptance metrics:
  - [ ] Signal precision target
  - [ ] Max drawdown limit
  - [ ] Daily loss cap

**Exit criteria**
- [ ] Inputs/outputs are frozen in a schema document
- [ ] Risk constraints approved

---

## Phase 1 — MVP Single-Agent (Price + Momentum) (3–7 days)
- [ ] Build standalone `Signal Agent` (paper mode only)
- [ ] Inputs: LTP, change %, previous close, basic trend
- [ ] Outputs: directional bias + candidate strike
- [ ] Add explainability block (why this signal was produced)
- [ ] Add confidence score (low/medium/high)
- [ ] Backtest on recent sessions (at least 20 days)

**Validation checklist**
- [ ] No runtime errors
- [ ] At least 95% data completeness for required fields
- [ ] Output schema valid for all test cases
- [ ] Risk guardrails always populated

**Exit criteria**
- [ ] Paper-trading report generated
- [ ] Baseline metrics documented

---

## Phase 2 — Institutional MVP (Options Engine) (1–2 weeks)
- [ ] Add `Options Analyst` module (still standalone)
- [ ] Add Greeks ingestion: Delta, Gamma, Theta, Vega
- [ ] Add IV regime detection (low/normal/high)
- [ ] Add ATM straddle price + breakout bands
- [ ] Add option-chain liquidity filters (OI, volume, spread)
- [ ] Merge signals in a `Decision Layer`

**Decision Layer rules**
- [ ] Momentum score
- [ ] Greeks score
- [ ] Volatility score
- [ ] Liquidity score
- [ ] Final weighted score + veto rules

**Exit criteria**
- [ ] False-signal reduction vs Phase 1
- [ ] Improved risk-adjusted return in paper mode

---

## Phase 3 — Multi-Agent Orchestration (2–3 weeks)
- [ ] Split responsibilities into agents:
  - [ ] Market Regime Agent
  - [ ] Options Structure Agent
  - [ ] Risk Officer Agent
  - [ ] Execution Planner Agent
- [ ] Add arbitration/consensus policy
- [ ] Add conflict resolution (e.g., risk veto > entry signal)
- [ ] Add agent memory policy (what persists, what expires)

**Exit criteria**
- [ ] Stable consensus across stress scenarios
- [ ] No policy violations in simulation runs

---

## Phase 4 — Advanced Institutional Features
- [ ] Regime-aware models (trend day vs mean reversion day)
- [ ] Event risk filter (RBI/Fed/CPI/earnings windows)
- [ ] Time-of-day behavior (open/midday/closing hour)
- [ ] Position sizing by volatility and confidence
- [ ] Portfolio-level exposure controls
- [ ] Live monitoring dashboard + alerts

**Exit criteria**
- [ ] Operational runbook complete
- [ ] Incident and rollback procedures tested

---

## Phase 5 — Controlled Integration (No Surprises)
- [ ] Add feature flag: `INSTITUTIONAL_AGENT_ENABLED=false` by default
- [ ] Shadow mode with current system (no order impact)
- [ ] Compare decisions side by side for 2+ weeks
- [ ] Approve go-live checklist
- [ ] Progressive rollout: 5% → 25% → 50% → 100%

**Go-live gates**
- [ ] Performance threshold met
- [ ] Risk threshold met
- [ ] Monitoring + alerting active
- [ ] Rollback tested

---

## Daily Execution Checklist (Operator)
- [ ] Data feed health check passed
- [ ] Model/agent version pinned
- [ ] Risk limits loaded
- [ ] Feature flags verified
- [ ] Dry-run sanity checks passed
- [ ] Session log enabled
- [ ] End-of-day report exported

---

## Minimum Artifacts Per Phase
- [ ] Phase design note
- [ ] Test cases and outcomes
- [ ] Backtest / paper-trading summary
- [ ] Risk incidents log (if any)
- [ ] Final phase sign-off
