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

## Batch Backtest Run
```bash
cd /workspaces/fyers/ClawWork/institutional_agents/phase1_scaffold
python batch_runner.py --input sample_batch_input.csv --outdir reports --tag demo
```

Outputs:
- `reports/demo_report.json` (full decisions + summary)
- `reports/demo_summary.json` (quick metrics only)

## Generate Markdown Report
```bash
cd /workspaces/fyers/ClawWork/institutional_agents/phase1_scaffold
python report_generator.py --report-json reports/demo_report.json
```

Output:
- `reports/demo_report.md`

## One-Command Pipeline
```bash
cd /workspaces/fyers/ClawWork/institutional_agents/phase1_scaffold
python pipeline_runner.py --input sample_batch_input.csv --outdir reports --tag demo
```

Pipeline output artifacts:
- `reports/demo_report.json`
- `reports/demo_summary.json`
- `reports/demo_report.md`

## Threshold Sweep (Tuning)
```bash
cd /workspaces/fyers/ClawWork/institutional_agents/phase1_scaffold
python threshold_sweep.py --input sample_batch_input.csv --outdir reports --tag tuning
```

Sweep output artifacts:
- `reports/tuning_threshold_sweep_summary.json`
- `reports/tuning_threshold_sweep_ranked.json`

## Generate Sweep Recommendation Report
```bash
cd /workspaces/fyers/ClawWork/institutional_agents/phase1_scaffold
python sweep_report_generator.py --summary-json reports/tuning_threshold_sweep_summary.json --ranked-json reports/tuning_threshold_sweep_ranked.json
```

Output:
- `reports/tuning_threshold_sweep_summary.md`

## Notes
- Paper mode only
- No order placement
- Extend logic iteratively as Phase 1 progresses
