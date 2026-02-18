# Phase 1 Scaffold (Standalone)

This folder provides a minimal, isolated scaffold for Phase 1 paper-mode signal development.

## Purpose
- Build baseline momentum signal logic
- Keep work isolated from production trading flow
- Standardize outputs for testing and reporting

## Files
- `models.py`: input/output contracts
- `config.py`: threshold and risk configuration
- `risk.py`: hard risk guards
- `signal_engine.py`: baseline decision logic
- `runner.py`: local execution on sample input
- `sample_input.json`: quick test data

## Run
```bash
cd /workspaces/fyers/ClawWork/institutional_agents/phase1_scaffold
python runner.py --input sample_input.json
```

## Notes
- Paper mode only
- No order placement
- Extend logic iteratively as Phase 1 progresses
