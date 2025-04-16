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

        self.logger.info("[BUY] 매수 시그널 판단 시작")

        ema = EMA(self.candles)
        bb = BollingerBands(self.candles)
        volume = VolumeSurgeDetector(self.candles)

        is_ema_cross = ema.is_golden_cross(short_period=3, long_period=9)
        is_bb_breakout = bb.is_band_breakout() == "upper"
        is_volume_surge = volume.is_surge(period=20, multiplier=1.5)

        self.logger.info(f"[BUY] EMA 정배열: {is_ema_cross}")
        self.logger.info(f"[BUY] 볼린저 상단 돌파: {is_bb_breakout}")
        self.logger.info(f"[BUY] 거래량 급증: {is_volume_surge}")

        result = is_ema_cross and is_bb_breakout and is_volume_surge
        self.logger.info(f"[BUY] 최종 매수 시그널: {result}")
        return result

    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float) -> bool:
        self.logger.info("[SELL] 매도 시그널 판단 시작")
        self.logger.info(f"[SELL] 현재가: {current_price}, 목표가: {target_price}, 손절가: {stop_loss_price}")

        if current_price >= target_price:
            self.logger.info("[SELL] 목표가 도달 → 익절")
            return True
        elif current_price <= stop_loss_price:
            self.logger.info("[SELL] 손절가 도달 → 손절")
            return True
        else:
            ema = EMA(self.candles)
            is_still_crossed = ema.is_golden_cross(short_period=3, long_period=9)
            result = not is_still_crossed
            self.logger.info(f"[SELL] EMA 정배열 유지 여부: {is_still_crossed} → 매도 판단: {result}")
            return result