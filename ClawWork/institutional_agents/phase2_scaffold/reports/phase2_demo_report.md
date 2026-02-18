# Phase 2 Report (phase2_demo)

## Run Metadata
- Input file: sample_batch_input.json
- Record count: 3

## Final Action Summary
- BUY_CALL: 1
- BUY_PUT: 1
- NO_TRADE: 1

## Options Signal Summary
- BULLISH: 1
- BEARISH: 1
- NEUTRAL: 0
- NO_TRADE (veto): 1
- Options veto %: 33.33%
- Average options score: 66.5

## Decision Sample
| # | Underlying | Momentum | Options | Final | Opt Score | Rationale |
|---|------------|----------|---------|-------|-----------|-----------|
| 1 | NIFTY50 | BUY_CALL | BULLISH | BUY_CALL | 83.75 | Momentum and options signals aligned bullish. |
| 2 | BANKNIFTY | BUY_PUT | BEARISH | BUY_PUT | 80.0 | Momentum and options signals aligned bearish. |
| 3 | SENSEX | NO_TRADE | NO_TRADE | NO_TRADE | 35.75 | Options guardrail veto. |