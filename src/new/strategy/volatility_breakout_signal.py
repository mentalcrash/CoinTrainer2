import logging
from typing import Tuple
from src.new.calculator.ema import EMA
from src.new.calculator.bollinger_bands import BollingerBands
from src.new.calculator.vlume_surge_detector import VolumeSurgeDetector
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.parameter.volatility_breakout_params import VolatilityBreakoutParams

class VolatilityBreakoutSignal(SignalStrategy):
    def __init__(self, market: str, params: VolatilityBreakoutParams):
        super().__init__(market, params)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.params = params

    def get_name(self) -> str:
        return "VolatilityBreakoutSignal"

    def should_buy(self) -> bool:
        candles = self.api_client.get_candles(self.market, interval="1m", limit=self.params.limit_candles).candles
        
        if len(candles) < self.params.limit_candles:
            self.logger.warning("[BUY] 캔들 수 부족으로 판단 불가 (필요: %d, 현재: %d)", self.params.limit_candles, len(candles))
            return False

        ema = EMA(candles)
        bb = BollingerBands(candles)
        volume = VolumeSurgeDetector(candles)

        is_ema_cross = ema.is_golden_cross(short_period=self.params.ema_short_period, long_period=self.params.ema_long_period)
        is_bb_breakout = bb.is_band_breakout(period=self.params.bb_period, multiplier=self.params.bb_multiplier) == "upper"
        is_volume_surge = volume.is_surge(period=self.params.volume_period, multiplier=self.params.volume_multiplier)

        result = is_ema_cross and is_bb_breakout and is_volume_surge

        return result
        
    def should_sell(self, current_price: float) -> Tuple[bool, str]:
        if current_price >= self.target_price:
            return True, f'목표가에 도달했습니다\n현재가 {current_price}, 목표가 {self.target_price}'
        elif current_price <= self.stop_loss_price:
            return True, f'손절가에 도달했습니다\n현재가 {current_price}, 손절가 {self.stop_loss_price}'
        return False, "매도 신호 없음"