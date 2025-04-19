import logging
from src.new.calculator.ema import EMA
from src.new.calculator.bollinger_bands import BollingerBands
from src.new.calculator.vlume_surge_detector import VolumeSurgeDetector
from src.new.strategy.signal_strategy import SignalStrategy

class VolatilityBreakoutSignal(SignalStrategy):
    def __init__(self, market: str):
        super().__init__(market)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def should_buy(self) -> bool:
        candles = self.api_client.get_candles(self.market, interval="1m", limit=30).candles
        
        if len(candles) < 30:
            self.logger.warning("[BUY] 캔들 수 부족으로 판단 불가 (필요: 30, 현재: %d)", len(candles))
            return False

        ema = EMA(candles)
        bb = BollingerBands(candles)
        volume = VolumeSurgeDetector(candles)

        is_ema_cross = ema.is_golden_cross(short_period=3, long_period=9)
        is_bb_breakout = bb.is_band_breakout() == "upper"
        is_volume_surge = volume.is_surge(period=20, multiplier=1.5)

        result = is_ema_cross and is_bb_breakout and is_volume_surge

        return result

    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float) -> bool:
        if current_price >= target_price:
            return True, f'목표가에 도달했습니다\n현재가 {current_price}, 목표가 {target_price}'
        elif current_price <= stop_loss_price:
            return True, f'손절가에 도달했습니다\n현재가 {current_price}, 손절가 {stop_loss_price}'
        return False, "매도 신호 없음"