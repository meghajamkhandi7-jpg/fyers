from __future__ import annotations

from typing import List

from contracts import OptionChainInput, OptionRow, OptionsSignal


class OptionsAnalyst:
    def __init__(self, max_spread_bps: float = 50.0, min_oi: float = 1000.0, min_volume: float = 500.0):
        self.max_spread_bps = max_spread_bps
        self.min_oi = min_oi
        self.min_volume = min_volume

    @staticmethod
    def _avg(rows: List[OptionRow], field: str) -> float:
        vals = [getattr(row, field) for row in rows if getattr(row, field) is not None]
        return float(sum(vals) / len(vals)) if vals else 0.0

    def _liquidity_pass(self, rows: List[OptionRow]) -> bool:
        if not rows:
            return False
        return all(row.oi >= self.min_oi and row.volume >= self.min_volume for row in rows)

    def _spread_pass(self, rows: List[OptionRow]) -> bool:
        if not rows:
            return False
        return all(row.spread_bps <= self.max_spread_bps for row in rows)

    def _greeks_score(self, rows: List[OptionRow], direction: str) -> float:
        avg_delta = self._avg(rows, "delta")
        avg_vega = self._avg(rows, "vega")

        if direction == "UP":
            score = (max(avg_delta, 0.0) * 100.0) + (avg_vega * 10.0)
        elif direction == "DOWN":
            score = (abs(min(avg_delta, 0.0)) * 100.0) + (avg_vega * 10.0)
        else:
            score = 25.0

        return float(max(0.0, min(score, 100.0)))

    @staticmethod
    def _vol_score(iv_percentile: float) -> float:
        if iv_percentile < 25:
            return 40.0
        if iv_percentile < 60:
            return 70.0
        if iv_percentile < 85:
            return 55.0
        return 35.0

    @staticmethod
    def _straddle_score(direction: str) -> float:
        if direction in {"UP", "DOWN"}:
            return 75.0
        return 30.0

    def analyze(self, chain_input: OptionChainInput) -> OptionsSignal:
        rows = chain_input.rows
        if not rows:
            return OptionsSignal(
                signal="NO_TRADE",
                confidence="LOW",
                preferred_strike_zone="NONE",
                options_score=0.0,
                rationale="No option-chain rows available.",
                liquidity_pass=False,
                spread_pass=False,
            )

        liquidity_pass = self._liquidity_pass(rows)
        spread_pass = self._spread_pass(rows)

        dir_hint = chain_input.straddle_breakout_direction
        greeks = self._greeks_score(rows, dir_hint)
        vol = self._vol_score(chain_input.iv_percentile)
        liq = 80.0 if liquidity_pass else 20.0
        straddle = self._straddle_score(dir_hint)

        options_score = 0.35 * greeks + 0.25 * vol + 0.25 * liq + 0.15 * straddle

        if not (liquidity_pass and spread_pass):
            signal = "NO_TRADE"
            confidence = "LOW"
            zone = "NONE"
            rationale = "Liquidity or spread guard failed."
        elif dir_hint == "UP" and options_score >= 55:
            signal = "BULLISH"
            confidence = "HIGH" if options_score >= 70 else "MEDIUM"
            zone = "OTM_1" if confidence == "HIGH" else "ATM"
            rationale = f"Bullish options profile (score={options_score:.2f})."
        elif dir_hint == "DOWN" and options_score >= 55:
            signal = "BEARISH"
            confidence = "HIGH" if options_score >= 70 else "MEDIUM"
            zone = "OTM_1" if confidence == "HIGH" else "ATM"
            rationale = f"Bearish options profile (score={options_score:.2f})."
        else:
            signal = "NEUTRAL"
            confidence = "LOW"
            zone = "NONE"
            rationale = f"No strong options edge (score={options_score:.2f})."

        return OptionsSignal(
            signal=signal,
            confidence=confidence,
            preferred_strike_zone=zone,
            options_score=round(options_score, 2),
            rationale=rationale,
            liquidity_pass=liquidity_pass,
            spread_pass=spread_pass,
        )
