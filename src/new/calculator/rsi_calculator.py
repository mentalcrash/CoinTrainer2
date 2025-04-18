from typing import List
from src.new.models.bithumb.response import Candle

class RSICalculator:
    def __init__(self, candles: List[Candle]):
        self.candles = sorted(candles, key=lambda c: c.timestamp)

    def calculate(self, period: int = 14) -> List[float]:
        """
        RSI 값을 계산합니다.

        Args:
            period (int): RSI 계산 기간 (기본: 14)

        Returns:
            List[float]: RSI 값 리스트 (처음 period-1개는 None 또는 0.0)
        """
        closes = [candle.trade_price for candle in self.candles]
        rsi_values = []

        gains = []
        losses = []

        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(abs(min(delta, 0)))

        for i in range(len(closes)):
            if i < period:
                rsi_values.append(0.0)  # 혹은 None
                continue

            avg_gain = sum(gains[i - period:i]) / period
            avg_loss = sum(losses[i - period:i]) / period

            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values