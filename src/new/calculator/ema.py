from src.new.models.bithumb.response import Candle
from typing import List

class EMA:
    def __init__(self, candles: List[Candle]):
        # 오름차순 정렬: 과거 → 현재
        self.candles = sorted(candles, key=lambda c: c.timestamp)
        
    def calculate(self, period: int) -> List[float]:
        """
        Candle 객체 리스트에서 종가를 기준으로 EMA를 계산합니다.

        Args:
            candles (List[Candle]): 시간순 정렬된 캔들 데이터 (과거 → 현재)
            period (int): EMA 기간

        Returns:
            List[Optional[float]]: EMA 값 리스트 (일부는 None)
        """
        prices = [candle.trade_price for candle in self.candles]
        
        if len(prices) < period:
            raise ValueError("캔들 데이터가 period보다 짧습니다.")
        
        ema_values = []
        multiplier = 2 / (period + 1)

        # 초기값은 SMA로 설정
        sma = sum(prices[:period]) / period
        ema_values = [None] * (period - 1) + [sma]

        # 나머지 EMA 계산
        for price in prices[period:]:
            prev_ema = ema_values[-1]
            ema = (price - prev_ema) * multiplier + prev_ema
            ema_values.append(ema)

        return ema_values
        
    def is_golden_cross(self, short_period: int = 3, long_period: int = 9) -> bool:
        """
        단기 정배열 여부 판단 (예: 3EMA > 9EMA)

        Args:
            short_period (int): 단기 EMA 기간 (기본: 3)
            long_period (int): 장기 EMA 기간 (기본: 9)

        Returns:
            bool: 최근 종가 기준으로 단기 EMA가 장기 EMA보다 높은지 여부
        """
        ema_short = self.calculate(short_period)
        ema_long = self.calculate(long_period)

        # 최신 EMA 값 비교
        latest_ema_short = ema_short[-1]
        latest_ema_long = ema_long[-1]

        # 둘 다 유효한 경우에만 비교
        if latest_ema_short is None or latest_ema_long is None:
            return False

        return latest_ema_short > latest_ema_long