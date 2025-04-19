import logging
from src.new.calculator.ema import EMA
from src.new.calculator.bollinger_bands import BollingerBands
from src.new.calculator.vlume_surge_detector import VolumeSurgeDetector
from src.new.strategy.signal_strategy import SignalStrategy

class VolatilityBreakoutSignal(SignalStrategy):
    def __init__(self, candles, ticker, orderbook):
        super().__init__(candles, ticker, orderbook)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def should_buy(self) -> bool:
        if len(self.candles) < 30:
            self.logger.warning("[BUY] 캔들 수 부족으로 판단 불가 (필요: 30, 현재: %d)", len(self.candles))
            return False

        ema = EMA(self.candles)
        bb = BollingerBands(self.candles)
        volume = VolumeSurgeDetector(self.candles)

        is_ema_cross = ema.is_golden_cross(short_period=3, long_period=9)
        is_bb_breakout = bb.is_band_breakout() == "upper"
        is_volume_surge = volume.is_surge(period=20, multiplier=1.5)

        result = is_ema_cross and is_bb_breakout and is_volume_surge

        return result

    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float) -> bool:
        if current_price >= target_price:
            return True
        elif current_price <= stop_loss_price:
            return True
        return False