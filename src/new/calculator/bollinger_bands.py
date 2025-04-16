from src.new.models.bithumb.response import Candle
from typing import List, Tuple, Optional, Literal
import statistics

class BollingerBands:
    def __init__(self, candles: List[Candle]):
        # 오름차순 정렬: 과거 → 현재
        self.candles = sorted(candles, key=lambda c: c.timestamp)

    def calculate(self, period: int = 20, multiplier: float = 2.0) -> List[Optional[Tuple[float, float, float]]]:
        """
        Bollinger Band를 계산합니다.

        Args:
            period (int): 기준 기간 (기본: 20)
            multiplier (float): 표준편차 배수 (기본: 2.0)

        Returns:
            List[Optional[Tuple[float, float, float]]]:
                [(상단밴드, 중앙밴드, 하단밴드), ...]
                일부는 None (초기 period 이전)
        """
        prices = [candle.trade_price for candle in self.candles]
        bands: List[Optional[Tuple[float, float, float]]] = []

        for i in range(len(prices)):
            if i < period - 1:
                bands.append(None)
                continue

            window = prices[i - period + 1:i + 1]
            sma = sum(window) / period
            stddev = statistics.stdev(window)

            upper_band = sma + (stddev * multiplier)
            lower_band = sma - (stddev * multiplier)

            bands.append((upper_band, sma, lower_band))

        return bands
    
    def is_band_breakout(self) -> Optional[Literal["upper", "lower"]]:
        """
        현재가가 볼린저 밴드의 상단 또는 하단을 돌파했는지 판단합니다.

        Returns:
            Optional[Literal["upper", "lower"]]: "upper", "lower", 또는 None
        """
        bands = self.calculate()
        latest_band = bands[-1]
        latest_price = self.candles[-1].trade_price

        if latest_band is None:
            return None

        upper, _, lower = latest_band

        if latest_price > upper:
            return "upper"
        elif latest_price < lower:
            return "lower"
        else:
            return None