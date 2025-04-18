from typing import List
from src.new.models.bithumb.response import Candle

class VWAPCalculator:
    def __init__(self, candles: List[Candle]):
        # 시간 오름차순 정렬
        self.candles = sorted(candles, key=lambda c: c.timestamp)

    def calculate(self, period: int = 20) -> List[float]:
        """
        VWAP 계산 (최근 period 개 기준 누적 계산)

        Args:
            period (int): 캔들 수 기준 (기본 20개)
        Returns:
            List[float]: 각 캔들에 대한 VWAP (시점별 누적)
        """
        vwap_values = []
        cumulative_pv = 0.0  # 누적 (price * volume)
        cumulative_volume = 0.0

        for i in range(len(self.candles)):
            price = self.candles[i].trade_price
            volume = self.candles[i].candle_acc_trade_volume

            cumulative_pv += price * volume
            cumulative_volume += volume

            if i < period - 1:
                vwap_values.append(0.0)  # 혹은 None
            else:
                vwap = cumulative_pv / cumulative_volume if cumulative_volume > 0 else 0.0
                vwap_values.append(vwap)

        return vwap_values