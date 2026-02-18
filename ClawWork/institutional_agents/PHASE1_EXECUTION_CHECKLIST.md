# Phase 1 Execution Checklist (Paper Mode)

## 1) Setup
- [ ] Confirm Phase 0 sign-off complete
- [ ] Lock thresholds version for this cycle
- [ ] Select 20+ recent sessions for evaluation
- [ ] Prepare output folder for run logs
- [ ] Run scaffold once: `python runner.py --input sample_input.json`

## 2) Build
- [ ] Implement isolated signal engine module
- [ ] Implement risk guard checks
- [ ] Implement strike suggestion logic
- [ ] Implement structured decision logging
- [ ] Replace sample input with real paper dataset slices

## 3) Validate
- [ ] Execute all Phase 1 test cases
- [ ] Resolve all critical failures
- [ ] Re-run full suite after fixes

## 4) Simulate
- [ ] Run paper mode on selected sessions
- [ ] Export daily decision logs
- [ ] Compute baseline metrics

## 5) Review
- [ ] Compare outcomes to acceptance metrics
- [ ] Document incidents and edge cases
- [ ] Capture improvement backlog for Phase 2

## 6) Exit Gate
- [ ] Baseline report generated
- [ ] Reliability and risk metrics pass
- [ ] Team sign-off for Phase 2 start
