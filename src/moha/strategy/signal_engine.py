"""Signal engine orchestrator: regime -> engine -> filters -> candidate."""
from __future__ import annotations

from typing import Optional, Tuple

from ..config import Config
from ..data.market_data import MarketData
from ..data.orderbook import DepthSnapshot
from ..types import EngineName, EngineSignal, FilterResult, RegimeSnapshot
from .expansion import ExpansionEngine
from .filters import FilterStack
from .momentum import MomentumEngine
from .pullback import PullbackEngine
from .regime import RegimeRouter


class SignalEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.regime = RegimeRouter(cfg)
        self.filters = FilterStack(cfg)
        self.engines = {
            EngineName.MOMENTUM: MomentumEngine(cfg),
            EngineName.PULLBACK: PullbackEngine(cfg),
            EngineName.EXPANSION: ExpansionEngine(cfg),
        }

    def evaluate(
        self,
        md: MarketData,
        depth: Optional[DepthSnapshot],
        now_ms: int,
    ) -> Tuple[Optional[EngineSignal], Optional[RegimeSnapshot], FilterResult]:
        regime = self.regime.classify(md, now_ms)
        if regime is None:
            return None, None, FilterResult(ok=False, reasons=["NO_REGIME"])

        engine_name = self.regime.pick_engine(regime)
        if engine_name is None:
            return None, regime, FilterResult(ok=False, reasons=["CHOP_OR_NO_ENGINE"])

        signal = self.engines[engine_name].evaluate(md)
        if signal is None:
            return None, regime, FilterResult(ok=False, reasons=["NO_ENGINE_TRIGGER"])

        fr = self.filters.check(signal, md, depth, now_ms)
        return signal, regime, fr
