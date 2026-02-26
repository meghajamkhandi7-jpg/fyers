from livebench.tools.direct_tools import institutional_run_paper_evaluation
from livebench.trading.paper_evaluator import compare_backtests, run_paper_backtest


def _candidate_rows():
    return [
        {"action": "BUY_CALL", "market_return_pct": 1.2},
        {"action": "BUY_PUT", "market_return_pct": -0.8},
        {"action": "NO_TRADE", "market_return_pct": 0.4},
        {"action": "BUY_CALL", "market_return_pct": -0.5},
        {"action": "BUY_PUT", "market_return_pct": 0.3},
    ]


def _baseline_rows():
    return [
        {"action": "NO_TRADE", "market_return_pct": 1.2},
        {"action": "BUY_CALL", "market_return_pct": -0.8},
        {"action": "NO_TRADE", "market_return_pct": 0.4},
        {"action": "BUY_CALL", "market_return_pct": -0.5},
        {"action": "NO_TRADE", "market_return_pct": 0.3},
    ]


def test_phase5_backtest_deterministic_for_same_input():
    first = run_paper_backtest(_candidate_rows(), transaction_cost_bps=5, slippage_bps=5)
    second = run_paper_backtest(_candidate_rows(), transaction_cost_bps=5, slippage_bps=5)

    assert first == second


def test_phase5_costs_reduce_cumulative_return():
    no_cost = run_paper_backtest(_candidate_rows(), transaction_cost_bps=0, slippage_bps=0)
    with_cost = run_paper_backtest(_candidate_rows(), transaction_cost_bps=10, slippage_bps=10)

    assert with_cost["performance"]["cumulative_return_pct"] < no_cost["performance"]["cumulative_return_pct"]


def test_phase5_compare_backtests_has_delta_metrics():
    result = compare_backtests(
        candidate_rows=_candidate_rows(),
        baseline_rows=_baseline_rows(),
        transaction_cost_bps=5,
        slippage_bps=5,
    )

    assert result["candidate"] is not None
    assert result["baseline"] is not None
    assert isinstance(result["delta"], dict)
    assert "sharpe" in result["delta"]


def test_phase5_tool_wrapper_success():
    payload = {
        "candidate_rows": _candidate_rows(),
        "baseline_rows": _baseline_rows(),
        "transaction_cost_bps": 5,
        "slippage_bps": 5,
        "annualization_factor": 252,
    }
    result = institutional_run_paper_evaluation.invoke({"payload": payload})

    assert result["success"] is True
    assert "report" in result
    assert "candidate" in result["report"]


def test_phase5_tool_wrapper_validation_error():
    result = institutional_run_paper_evaluation.invoke({"payload": {"candidate_rows": "bad"}})

    assert result["success"] is False
    assert "candidate_rows" in result["error"]
