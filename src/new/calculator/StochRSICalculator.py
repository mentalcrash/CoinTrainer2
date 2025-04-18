from typing import List, Tuple
from src.new.models.bithumb.response import Candle
from src.new.calculator.rsi_calculator import RSICalculator  # 앞서 만든 RSI 클래스

class StochRSICalculator:
    def __init__(self, candles: List[Candle]):
        self.candles = candles
        

    def calculate(self, stoch_period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[List[float], List[float]]:
        """
        Stochastic RSI 계산 (0~1 정규화)

        Returns:
            %K, %D 리스트 (모두 0.0~1.0 범위)
        """
        rsi_values = RSICalculator(self.candles).calculate(period=stoch_period)
        
        stoch_rsi = []

        for i in range(len(rsi_values)):
            if i < stoch_period:
                stoch_rsi.append(0.0)
                continue

            window = rsi_values[i - stoch_period + 1:i + 1]
            min_rsi = min(window)
            max_rsi = max(window)
            if max_rsi - min_rsi == 0:
                stoch_rsi.append(0.0)
            else:
                value = (rsi_values[i] - min_rsi) / (max_rsi - min_rsi)
                stoch_rsi.append(value)

        # Smooth %K
        def moving_avg(data: List[float], period: int) -> List[float]:
            result = []
            for i in range(len(data)):
                if i < period:
                    result.append(0.0)
                else:
                    avg = sum(data[i - period + 1:i + 1]) / period
                    result.append(avg)
            return result

        percent_k = moving_avg(stoch_rsi, smooth_k)
        percent_d = moving_avg(percent_k, smooth_d)

        return percent_k, percent_d