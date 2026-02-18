from dataclasses import dataclass
from typing import List, Literal, Optional


@dataclass
class OptionRow:
    strike: int
    option_type: Literal["CE", "PE"]
    ltp: float
    oi: float
    oi_change: float
    volume: float
    spread_bps: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


@dataclass
class OptionsSignal:
    signal: Literal["BULLISH", "BEARISH", "NEUTRAL", "NO_TRADE"]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    preferred_strike_zone: Literal["ITM_1", "ATM", "OTM_1", "NONE"]
    options_score: float
    rationale: str
    liquidity_pass: bool
    spread_pass: bool


@dataclass
class MomentumSignal:
    action: Literal["BUY_CALL", "BUY_PUT", "NO_TRADE"]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]


@dataclass
class FinalDecision:
    action: Literal["BUY_CALL", "BUY_PUT", "NO_TRADE"]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    rationale: str


@dataclass
class OptionChainInput:
    underlying: Literal["NIFTY50", "BANKNIFTY", "SENSEX"]
    underlying_change_pct: float
    iv_percentile: float
    straddle_breakout_direction: Literal["UP", "DOWN", "NONE"]
    rows: List[OptionRow]
