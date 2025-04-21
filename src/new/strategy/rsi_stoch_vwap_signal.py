from new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.models.bithumb.response import Candle, Ticker, Orderbook
from src.new.calculator.rsi_calculator import RSICalculator
from src.new.calculator.stoch_rsi_calculator import StochRSICalculator
from src.new.calculator.vwap_calculator import VWAPCalculator
from typing import Tuple

class RSIStochVWAPSignal(SignalStrategy):
    def should_buy(self) -> bool:
        candles = self.api_client.get_candles(self.market, interval="1m", limit=30).candles
        
        if len(candles) < 30:
            return False

        # 1. RSI 50선 돌파
        rsi = RSICalculator(candles).calculate(period=14)
        is_rsi_break = rsi[-2] < 50 and rsi[-1] >= 50

        # 2. StochRSI 골든크로스
        stoch_k, stoch_d = StochRSICalculator(candles).calculate(stoch_period=14)
        is_stoch_cross = stoch_k[-2] < stoch_d[-2] and stoch_k[-1] > stoch_d[-1]

        # 3. VWAP 상회
        vwap = VWAPCalculator(candles).calculate(period=20)
        current_price = candles[-1].trade_price
        is_above_vwap = current_price > vwap[-1]

        # 종합 판단
        return is_rsi_break and is_stoch_cross and is_above_vwap

    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float) -> Tuple[bool, str]:
        if current_price >= target_price:
            return True, f'목표가에 도달했습니다\n현재가 {current_price}, 목표가 {target_price}'
        elif current_price <= stop_loss_price:
            return True, f'손절가에 도달했습니다\n현재가 {current_price}, 손절가 {stop_loss_price}'
        else:
            # RSI가 50 아래로 내려가면 조정 가능성
            rsi = RSICalculator(self.candles).calculate(period=14)
            return rsi[-1] < 50, f'RSI가 50 아래로 내려갔습니다\n현재 RSI: {rsi[-1]}\n현재가 {current_price}, 목표가 {target_price}, 손절가 {stop_loss_price}'