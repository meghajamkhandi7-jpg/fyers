from contracts import FinalDecision, MomentumSignal, OptionsSignal


class DecisionLayer:
    def merge(self, momentum: MomentumSignal, options_signal: OptionsSignal) -> FinalDecision:
        if options_signal.signal == "NO_TRADE":
            return FinalDecision(
                action="NO_TRADE",
                confidence="LOW",
                rationale="Options guardrail veto.",
            )

        if momentum.action == "BUY_CALL" and options_signal.signal == "BULLISH":
            return FinalDecision(
                action="BUY_CALL",
                confidence="HIGH" if options_signal.confidence == "HIGH" else "MEDIUM",
                rationale="Momentum and options signals aligned bullish.",
            )

        if momentum.action == "BUY_PUT" and options_signal.signal == "BEARISH":
            return FinalDecision(
                action="BUY_PUT",
                confidence="HIGH" if options_signal.confidence == "HIGH" else "MEDIUM",
                rationale="Momentum and options signals aligned bearish.",
            )

        return FinalDecision(
            action="NO_TRADE",
            confidence="LOW",
            rationale="Momentum and options signals not aligned.",
        )
