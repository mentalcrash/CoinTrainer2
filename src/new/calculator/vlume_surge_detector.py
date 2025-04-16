from src.new.models.bithumb.response import Candle
from typing import List

class VolumeSurgeDetector:
    def __init__(self, candles: List[Candle]):
        self.candles = sorted(candles, key=lambda c: c.timestamp)

    def is_surge(self, period: int = 20, multiplier: float = 1.5) -> bool:
        """
        최근 거래량이 평균 대비 얼마나 급증했는지 감지

        Args:
            period (int): 거래량 평균 계산 기준 봉 수
            multiplier (float): 평균 대비 증가 배수 기준

        Returns:
            bool: 거래량 급증 여부
        """
        if len(self.candles) < period:
            return False

        volumes = [c.candle_acc_trade_volume for c in self.candles[-period-1:-1]]
        avg_volume = sum(volumes) / len(volumes)
        latest_volume = self.candles[-1].candle_acc_trade_volume

        return latest_volume > avg_volume * multiplier